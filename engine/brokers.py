"""
Broker implementations — simulated and abstract base.

The simulated broker models realistic execution:
- Configurable slippage (basis points)
- Commission per trade
- Partial fills for large orders
- Random rejection rate (for testing error handling)

Live broker adapters would implement the same interface
to plug in without changing strategy code.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
import random
from datetime import datetime, timezone

from models.orders import Order, Side
from models.fills import Fill


class Broker(ABC):
    """Abstract broker interface. All brokers implement this."""

    @abstractmethod
    def submit_order(self, order: Order, current_price: float) -> Fill | None:
        """
        Submit an order for execution.

        Returns a Fill if executed, None if rejected/pending.
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order. Returns True if successfully cancelled."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Broker identifier."""
        pass


class SimulatedBroker(Broker):
    """
    Simulated broker with realistic execution modeling.

    Models slippage, commissions, and occasional rejections.
    Used for strategy development and backtesting.
    """

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        slippage_bps: float = 5.0,
        commission_per_trade: float = 2.50,
        rejection_rate: float = 0.0,
        partial_fill_rate: float = 0.0,
        seed: int | None = None,
    ):
        self.capital = initial_capital
        self.initial_capital = initial_capital
        self.slippage_bps = slippage_bps
        self.commission_per_trade = commission_per_trade
        self.rejection_rate = rejection_rate
        self.partial_fill_rate = partial_fill_rate
        self._rng = random.Random(seed)
        self._pending_orders: dict[str, Order] = {}
        self._open_positions_value: float = 0.0

    def update_positions_value(self, value: float) -> None:
        """Update the mark-to-market value of open positions (unrealized P&L)."""
        self._open_positions_value = value

    @property
    def name(self) -> str:
        return "simulated"

    def submit_order(self, order: Order, current_price: float) -> Fill | None:
        """
        Simulate order execution with slippage and commissions.

        Buy orders fill at ask (price + slippage).
        Sell orders fill at bid (price - slippage).
        """
        # Random rejection (for testing error handling paths)
        if self._rng.random() < self.rejection_rate:
            return None

        # Calculate fill price with slippage
        slippage = current_price * (self.slippage_bps / 10_000)

        if order.side == Side.BUY:
            fill_price = current_price + slippage
        else:
            fill_price = current_price - slippage

        # Partial fill simulation
        fill_quantity = order.remaining_quantity
        if self._rng.random() < self.partial_fill_rate:
            fill_quantity = max(1.0, fill_quantity * self._rng.uniform(0.3, 0.7))
            fill_quantity = round(fill_quantity, 4)

        # Check if we have enough capital for a buy
        if order.side == Side.BUY:
            cost = fill_price * fill_quantity
            if cost > self.capital:
                return None  # Insufficient funds
            self.capital -= cost
        else:
            # Sell: return capital
            self.capital += fill_price * fill_quantity

        # Deduct commission
        self.capital -= self.commission_per_trade

        return Fill(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side.value,
            quantity=fill_quantity,
            price=round(fill_price, 4),
            expected_price=current_price,
            commission=self.commission_per_trade,
        )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        if order_id in self._pending_orders:
            del self._pending_orders[order_id]
            return True
        return False

    @property
    def equity(self) -> float:
        """Current account equity (cash + unrealized P&L from open positions)."""
        return self.capital + self._open_positions_value

    @property
    def return_pct(self) -> float:
        """Account return percentage."""
        return (self.capital - self.initial_capital) / self.initial_capital
