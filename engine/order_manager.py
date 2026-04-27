"""
Order lifecycle management with state machine enforcement.

The OrderManager is responsible for:
- Creating orders from signals
- Tracking all orders by ID and state
- Enforcing state machine transitions
- Emitting events for every state change
"""

from __future__ import annotations
from typing import Optional

from models.orders import Order, OrderState, OrderType, Side, TimeInForce
from models.signals import Signal
from models.fills import Fill
from models.events import (
    OrderCreated, OrderSubmitted, OrderRejected,
    OrderFilled, OrderPartialFill, OrderCancelled,
)
from engine.event_store import EventStore


class OrderManager:
    """
    Manages the full lifecycle of orders.

    Every state change emits an event to the event store.
    Orders are indexed by ID for O(1) lookup.
    """

    def __init__(self, event_store: EventStore):
        self._orders: dict[str, Order] = {}
        self._event_store = event_store

    def create_order(
        self,
        symbol: str,
        side: Side,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.DAY,
        strategy_id: Optional[str] = None,
    ) -> Order:
        """Create a new order and emit OrderCreated event."""
        order = Order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            strategy_id=strategy_id,
        )

        self._orders[order.order_id] = order

        self._event_store.append(OrderCreated(
            order_id=order.order_id,
            symbol=symbol,
            side=side.value,
            quantity=quantity,
            order_type=order_type.value,
            limit_price=limit_price,
        ))

        return order

    def submit(self, order_id: str, broker_name: str = "simulated") -> None:
        """Mark an order as submitted to a broker."""
        order = self._get_order(order_id)
        order.transition_to(OrderState.PENDING)
        order.transition_to(OrderState.SUBMITTED)

        self._event_store.append(OrderSubmitted(
            order_id=order_id,
            broker=broker_name,
        ))

    def reject(self, order_id: str, reason: str) -> None:
        """Reject an order with a reason."""
        order = self._get_order(order_id)
        order.transition_to(OrderState.REJECTED, reason=reason)

        self._event_store.append(OrderRejected(
            order_id=order_id,
            reason=reason,
        ))

    def apply_fill(self, order_id: str, fill: Fill) -> None:
        """Apply a fill to an order and emit appropriate event."""
        order = self._get_order(order_id)
        was_partial = order.state == OrderState.PARTIAL_FILL
        order.apply_fill(fill.price, fill.quantity)

        if order.state == OrderState.FILLED:
            self._event_store.append(OrderFilled(
                order_id=order_id,
                fill_price=fill.price,
                quantity=fill.quantity,
                slippage_bps=fill.slippage_bps,
                commission=fill.commission,
            ))
        else:
            self._event_store.append(OrderPartialFill(
                order_id=order_id,
                fill_price=fill.price,
                filled_quantity=order.filled_quantity,
                remaining_quantity=order.remaining_quantity,
            ))

    def cancel(self, order_id: str, reason: str = "User requested") -> None:
        """Cancel an order."""
        order = self._get_order(order_id)
        order.transition_to(OrderState.CANCELLED)

        self._event_store.append(OrderCancelled(
            order_id=order_id,
            reason=reason,
        ))

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID (returns None if not found)."""
        return self._orders.get(order_id)

    def get_open_orders(self) -> list[Order]:
        """Get all non-terminal orders."""
        return [o for o in self._orders.values() if not o.is_terminal]

    def get_orders_by_symbol(self, symbol: str) -> list[Order]:
        """Get all orders for a symbol."""
        return [o for o in self._orders.values() if o.symbol == symbol]

    def get_orders_by_state(self, state: OrderState) -> list[Order]:
        """Get all orders in a specific state."""
        return [o for o in self._orders.values() if o.state == state]

    @property
    def total_orders(self) -> int:
        return len(self._orders)

    def _get_order(self, order_id: str) -> Order:
        """Get an order or raise ValueError."""
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        return order
