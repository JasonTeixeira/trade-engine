"""
Order model with strict state machine transitions.

An order can only move through valid states. Invalid transitions
raise InvalidTransition — this prevents the class of bugs where
orders end up in impossible states (e.g., a filled order that
gets cancelled).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4


class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class TimeInForce(Enum):
    DAY = "DAY"        # Cancel at end of session
    GTC = "GTC"        # Good till cancelled
    IOC = "IOC"        # Immediate or cancel
    FOK = "FOK"        # Fill or kill (all or nothing)


class OrderState(Enum):
    CREATED = "CREATED"
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class InvalidTransition(Exception):
    """Raised when an order state transition is not allowed."""
    pass


# Valid state transitions — the order state machine
VALID_TRANSITIONS: dict[OrderState, set[OrderState]] = {
    OrderState.CREATED: {OrderState.PENDING, OrderState.REJECTED},
    OrderState.PENDING: {OrderState.SUBMITTED, OrderState.REJECTED, OrderState.CANCELLED},
    OrderState.SUBMITTED: {OrderState.PARTIAL_FILL, OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED},
    OrderState.PARTIAL_FILL: {OrderState.FILLED, OrderState.CANCELLED},
    OrderState.FILLED: set(),       # Terminal state
    OrderState.CANCELLED: set(),    # Terminal state
    OrderState.REJECTED: set(),     # Terminal state
}


@dataclass
class Order:
    """
    Represents a trading order with strict state machine enforcement.

    State transitions are validated — calling transition_to() with an
    invalid target state raises InvalidTransition.
    """
    symbol: str
    side: Side
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY

    # Auto-generated
    order_id: str = field(default_factory=lambda: f"ORD-{uuid4().hex[:8].upper()}")
    state: OrderState = field(default=OrderState.CREATED)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # Fill tracking
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    fill_count: int = 0

    # Metadata
    strategy_id: Optional[str] = None
    rejection_reason: Optional[str] = None

    @property
    def remaining_quantity(self) -> float:
        """Quantity still to be filled."""
        return self.quantity - self.filled_quantity

    @property
    def is_terminal(self) -> bool:
        """Whether the order is in a final state (no more transitions possible)."""
        return self.state in {OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED}

    @property
    def fill_ratio(self) -> float:
        """Percentage of order that has been filled (0.0 - 1.0)."""
        if self.quantity == 0:
            return 0.0
        return self.filled_quantity / self.quantity

    def transition_to(self, new_state: OrderState, reason: Optional[str] = None) -> None:
        """
        Transition the order to a new state.

        Raises InvalidTransition if the transition is not allowed
        by the state machine.
        """
        valid_next = VALID_TRANSITIONS.get(self.state, set())

        if new_state not in valid_next:
            raise InvalidTransition(
                f"Cannot transition order {self.order_id} from "
                f"{self.state.value} to {new_state.value}. "
                f"Valid transitions: {[s.value for s in valid_next]}"
            )

        self.state = new_state
        self.updated_at = datetime.utcnow()

        if reason and new_state == OrderState.REJECTED:
            self.rejection_reason = reason

    def apply_fill(self, fill_price: float, fill_quantity: float) -> None:
        """
        Apply a fill (full or partial) to the order.

        Updates average fill price using volume-weighted calculation.
        Transitions state to PARTIAL_FILL or FILLED automatically.
        """
        if fill_quantity <= 0:
            raise ValueError("Fill quantity must be positive")

        if fill_quantity > self.remaining_quantity + 0.0001:  # Float tolerance
            raise ValueError(
                f"Fill quantity ({fill_quantity}) exceeds remaining "
                f"quantity ({self.remaining_quantity})"
            )

        # Volume-weighted average price
        total_value = (self.average_fill_price * self.filled_quantity) + (fill_price * fill_quantity)
        self.filled_quantity += fill_quantity
        self.average_fill_price = total_value / self.filled_quantity
        self.fill_count += 1

        # Auto-transition state
        if abs(self.remaining_quantity) < 0.0001:  # Fully filled
            self.transition_to(OrderState.FILLED)
        elif self.state == OrderState.SUBMITTED:
            self.transition_to(OrderState.PARTIAL_FILL)

    def __repr__(self) -> str:
        return (
            f"Order(id={self.order_id}, {self.side.value} {self.quantity} {self.symbol} "
            f"@ {self.order_type.value}, state={self.state.value}, "
            f"filled={self.filled_quantity}/{self.quantity})"
        )
