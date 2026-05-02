"""
Position tracking with real-time P&L calculation.

Positions track the aggregate state of all fills for a symbol.
P&L splits into unrealized (open positions) and realized (closed trades).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from models.orders import Side


@dataclass
class Position:
    """
    Represents an open position in a single instrument.

    Tracks entry price (volume-weighted average of fills),
    current market price, and splits P&L into unrealized and realized.
    """
    symbol: str
    side: Side
    quantity: float
    entry_price: float
    current_price: float = 0.0
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # P&L tracking
    realized_pnl: float = 0.0
    commission_paid: float = 0.0

    # Contract multiplier (e.g., ES futures = $50 per point)
    multiplier: float = 1.0

    @property
    def unrealized_pnl(self) -> float:
        """Mark-to-market P&L on the open position."""
        if self.quantity == 0 or self.current_price == 0:
            return 0.0

        if self.side == Side.BUY:
            return (self.current_price - self.entry_price) * self.quantity * self.multiplier
        else:
            return (self.entry_price - self.current_price) * self.quantity * self.multiplier

    @property
    def total_pnl(self) -> float:
        """Unrealized + realized P&L."""
        return self.unrealized_pnl + self.realized_pnl

    @property
    def return_pct(self) -> float:
        """Return percentage on the position."""
        if self.entry_price == 0:
            return 0.0
        if self.side == Side.BUY:
            return (self.current_price - self.entry_price) / self.entry_price
        else:
            return (self.entry_price - self.current_price) / self.entry_price

    @property
    def notional_value(self) -> float:
        """Current notional value of the position."""
        return self.current_price * self.quantity * self.multiplier

    @property
    def is_open(self) -> bool:
        """Whether the position has remaining quantity."""
        return self.quantity > 0

    def update_price(self, price: float) -> None:
        """Update the current market price for P&L calculation."""
        self.current_price = price
        self.updated_at = datetime.now(timezone.utc)

    def reduce(self, quantity: float, fill_price: float) -> float:
        """
        Reduce the position by the given quantity at the given price.

        Returns the realized P&L from the reduction.
        """
        if quantity > self.quantity:
            raise ValueError(
                f"Cannot reduce position by {quantity} — "
                f"only {self.quantity} held"
            )

        # Calculate realized P&L for the closed portion
        if self.side == Side.BUY:
            pnl = (fill_price - self.entry_price) * quantity * self.multiplier
        else:
            pnl = (self.entry_price - fill_price) * quantity * self.multiplier

        self.realized_pnl += pnl
        self.quantity -= quantity
        self.updated_at = datetime.now(timezone.utc)

        return pnl

    def add(self, quantity: float, fill_price: float) -> None:
        """
        Add to the position (scale in). Updates average entry price.
        """
        # Volume-weighted average entry price
        total_cost = (self.entry_price * self.quantity) + (fill_price * quantity)
        self.quantity += quantity
        self.entry_price = total_cost / self.quantity
        self.updated_at = datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return (
            f"Position({self.side.value} {self.quantity} {self.symbol} "
            f"@ {self.entry_price:.2f}, "
            f"pnl={self.unrealized_pnl:+.2f} unrealized, "
            f"{self.realized_pnl:+.2f} realized)"
        )
