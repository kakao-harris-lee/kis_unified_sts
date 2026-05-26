"""Signal-to-paper-order bridge for Strategy Lab."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from shared.strategy_lab.config import get_default_order_amount
from shared.strategy_lab.schema import (
    LabSignal,
    OrderStatus,
    OrderTicket,
    PaperOrder,
    PaperPosition,
    SignalSide,
    SignalStatus,
)
from shared.strategy_lab.store import StrategyLabStore


class StrategyLabOrderBridge:
    """Build and execute paper-only orders from generated signals."""

    def __init__(self, store: StrategyLabStore | None = None) -> None:
        self.store = store or StrategyLabStore()

    def create_ticket(
        self,
        signal: LabSignal,
        *,
        quantity: int | None = None,
        order_amount: float | None = None,
    ) -> OrderTicket:
        if signal.side == SignalSide.HOLD:
            return self._rejected_ticket(
                signal,
                "HOLD signals cannot create paper orders",
            )
        if signal.orderability != "paper_orderable":
            return self._rejected_ticket(signal, signal.orderability)

        position = self.store.get_position(signal.draft_id, signal.symbol)
        requested_amount = order_amount or self._risk_order_amount(signal)

        if signal.side == SignalSide.SELL:
            if position is None or position.quantity <= 0:
                return self._rejected_ticket(
                    signal,
                    "No matching Strategy Lab paper position for SELL",
                )
            resolved_quantity = quantity or position.quantity
            resolved_quantity = min(resolved_quantity, position.quantity)
            resolved_amount = resolved_quantity * signal.reference_price
            impact = f"Reduce paper position by {resolved_quantity}"
        else:
            resolved_quantity = quantity or self._quantity_from_amount(
                requested_amount,
                signal.reference_price,
            )
            resolved_amount = resolved_quantity * signal.reference_price
            impact = f"Open or add {resolved_quantity} paper shares/contracts"

        if resolved_quantity <= 0:
            return self._rejected_ticket(signal, "Resolved quantity is zero")

        ticket = OrderTicket(
            signal_id=signal.signal_id,
            draft_id=signal.draft_id,
            strategy_name=signal.strategy_name,
            asset_class=signal.asset_class,
            symbol=signal.symbol,
            side=signal.side,
            quantity=resolved_quantity,
            order_amount=resolved_amount,
            estimated_price=signal.reference_price,
            position_impact=impact,
        )
        self.store.store_ticket(ticket)
        self.store.mark_signal_status(
            signal,
            SignalStatus.ORDER_TICKET_CREATED,
        )
        return ticket

    def submit_paper_order(self, ticket: OrderTicket) -> PaperOrder:
        if ticket.status != OrderStatus.READY:
            order = PaperOrder(
                ticket_id=ticket.ticket_id,
                signal_id=ticket.signal_id,
                draft_id=ticket.draft_id,
                asset_class=ticket.asset_class,
                symbol=ticket.symbol,
                side=ticket.side,
                quantity=ticket.quantity,
                price=ticket.estimated_price,
                status=OrderStatus.REJECTED,
                reason=ticket.reason or "Ticket is not orderable",
            )
            self.store.store_order(order)
            return order

        signal = self.store.get_signal(ticket.signal_id)
        position = self.store.get_position(ticket.draft_id, ticket.symbol)
        original_position_id = position.position_id if position is not None else None
        fill_id = f"fill_{uuid4().hex}"

        if ticket.side == SignalSide.BUY:
            position = self._apply_buy(ticket, position)
            realized_pnl = 0.0
            status = OrderStatus.FILLED
            reason = None
        else:
            if position is None or position.quantity < ticket.quantity:
                order = PaperOrder(
                    ticket_id=ticket.ticket_id,
                    signal_id=ticket.signal_id,
                    draft_id=ticket.draft_id,
                    asset_class=ticket.asset_class,
                    symbol=ticket.symbol,
                    side=ticket.side,
                    quantity=ticket.quantity,
                    price=ticket.estimated_price,
                    status=OrderStatus.REJECTED,
                    reason="No sufficient Strategy Lab paper position",
                )
                self.store.store_order(order)
                if signal is not None:
                    self.store.mark_signal_status(
                        signal,
                        SignalStatus.PAPER_REJECTED,
                        paper_order_id=order.order_id,
                    )
                return order
            position, realized_pnl = self._apply_sell(ticket, position)
            status = OrderStatus.FILLED
            reason = None

        position_id = position.position_id if position is not None else original_position_id
        order = PaperOrder(
            ticket_id=ticket.ticket_id,
            signal_id=ticket.signal_id,
            draft_id=ticket.draft_id,
            asset_class=ticket.asset_class,
            symbol=ticket.symbol,
            side=ticket.side,
            quantity=ticket.quantity,
            price=ticket.estimated_price,
            status=status,
            fill_id=fill_id,
            position_id=position_id,
            realized_pnl=realized_pnl,
            reason=reason,
        )
        self.store.store_order(order)
        if signal is not None:
            self.store.mark_signal_status(
                signal,
                SignalStatus.PAPER_FILLED,
                paper_order_id=order.order_id,
                fill_id=fill_id,
                position_id=position_id,
            )
        return order

    def _apply_buy(
        self,
        ticket: OrderTicket,
        position: PaperPosition | None,
    ) -> PaperPosition:
        if position is None:
            position = PaperPosition(
                draft_id=ticket.draft_id,
                asset_class=ticket.asset_class,
                symbol=ticket.symbol,
                quantity=ticket.quantity,
                avg_price=ticket.estimated_price,
            )
        else:
            new_quantity = position.quantity + ticket.quantity
            avg_price = (
                position.avg_price * position.quantity
                + ticket.estimated_price * ticket.quantity
            ) / new_quantity
            position = position.model_copy(
                update={
                    "quantity": new_quantity,
                    "avg_price": avg_price,
                    "updated_at": datetime.now(UTC),
                }
            )
        self.store.store_position(position)
        return position

    def _apply_sell(
        self,
        ticket: OrderTicket,
        position: PaperPosition,
    ) -> tuple[PaperPosition | None, float]:
        realized_pnl = (ticket.estimated_price - position.avg_price) * ticket.quantity
        remaining = position.quantity - ticket.quantity
        if remaining <= 0:
            self.store.delete_position(ticket.draft_id, ticket.symbol)
            return None, realized_pnl
        updated = position.model_copy(
            update={
                "quantity": remaining,
                "realized_pnl": position.realized_pnl + realized_pnl,
                "updated_at": datetime.now(UTC),
            }
        )
        self.store.store_position(updated)
        return updated, realized_pnl

    def _risk_order_amount(self, signal: LabSignal) -> float:
        value = signal.risk_snapshot.get("order_amount")
        if value is not None:
            return float(value)
        return get_default_order_amount()

    def _quantity_from_amount(self, amount: float, price: float) -> int:
        return max(1, int(amount // price))

    def _rejected_ticket(self, signal: LabSignal, reason: str) -> OrderTicket:
        ticket = OrderTicket(
            signal_id=signal.signal_id,
            draft_id=signal.draft_id,
            strategy_name=signal.strategy_name,
            asset_class=signal.asset_class,
            symbol=signal.symbol,
            side=signal.side,
            quantity=1,
            order_amount=signal.reference_price,
            estimated_price=signal.reference_price,
            position_impact="No paper position change",
            status=OrderStatus.REJECTED,
            reason=reason,
        )
        self.store.store_ticket(ticket)
        return ticket
