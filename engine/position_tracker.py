"""
Position tracking with P&L calculation.

Manages open positions across all symbols. Handles position
opening, scaling in/out, and closing with realized P&L tracking.
"""

from __future__ import annotations
from typing import Optional

from models.orders import Side
from models.positions import Position
from models.fills import Fill
from models.events import PositionOpened, PositionClosed, PositionUpdated
from engine.event_store import EventStore


class PositionTracker:
    """
    Tracks all open positions and calculates P&L.

    Positions are keyed by symbol — one position per symbol.
    Opposite-side fills reduce/close positions.
    """

    def __init__(self, event_store: EventStore):
        self._positions: dict[str, Position] = {}
        self._closed_positions: list[Position] = []
        self._event_store = event_store

    def apply_fill(self, fill: Fill) -> None:
        """
        Apply a fill to the position tracker.

        If no position exists: open a new one.
        If same side: add to position (scale in).
        If opposite side: reduce or close position.
        """
        existing = self._positions.get(fill.symbol)
        fill_side = Side.BUY if fill.side == "BUY" else Side.SELL

        if existing is None:
            # Open new position
            self._open_position(fill, fill_side)
        elif existing.side == fill_side:
            # Same direction — scale in
            existing.add(fill.quantity, fill.price)
            self._event_store.append(PositionUpdated(
                symbol=fill.symbol,
                quantity=existing.quantity,
                entry_price=existing.entry_price,
                unrealized_pnl=existing.unrealized_pnl,
            ))
        else:
            # Opposite direction — reduce or close
            self._reduce_position(existing, fill)

    def update_price(self, symbol: str, price: float) -> None:
        """Update mark-to-market price for a position."""
        position = self._positions.get(symbol)
        if position:
            position.update_price(price)

    def update_all_prices(self, prices: dict[str, float]) -> None:
        """Update prices for all tracked symbols."""
        for symbol, price in prices.items():
            self.update_price(symbol, price)

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get the current position for a symbol."""
        return self._positions.get(symbol)

    def get_all_positions(self) -> dict[str, Position]:
        """Get all open positions."""
        return dict(self._positions)

    def get_closed_positions(self) -> list[Position]:
        """Get all closed positions (for realized P&L)."""
        return list(self._closed_positions)

    @property
    def total_unrealized_pnl(self) -> float:
        """Sum of unrealized P&L across all open positions."""
        return sum(p.unrealized_pnl for p in self._positions.values())

    @property
    def total_realized_pnl(self) -> float:
        """Sum of realized P&L from all closed positions."""
        return sum(p.realized_pnl for p in self._closed_positions)

    @property
    def total_pnl(self) -> float:
        """Total P&L (unrealized + realized)."""
        return self.total_unrealized_pnl + self.total_realized_pnl

    @property
    def open_position_count(self) -> int:
        return len(self._positions)

    def has_position(self, symbol: str) -> bool:
        return symbol in self._positions

    def _open_position(self, fill: Fill, side: Side) -> None:
        """Open a new position from a fill."""
        position = Position(
            symbol=fill.symbol,
            side=side,
            quantity=fill.quantity,
            entry_price=fill.price,
            current_price=fill.price,
        )
        self._positions[fill.symbol] = position

        self._event_store.append(PositionOpened(
            symbol=fill.symbol,
            side=side.value,
            quantity=fill.quantity,
            entry_price=fill.price,
        ))

    def _reduce_position(self, position: Position, fill: Fill) -> None:
        """Reduce or close a position from an opposite-side fill."""
        if fill.quantity >= position.quantity:
            # Full close
            pnl = position.reduce(position.quantity, fill.price)
            hold_duration = (fill.timestamp - position.opened_at).total_seconds()

            self._closed_positions.append(position)
            del self._positions[fill.symbol]

            self._event_store.append(PositionClosed(
                symbol=fill.symbol,
                realized_pnl=pnl,
                hold_duration_seconds=hold_duration,
            ))

            # If fill quantity exceeds position, open a new position in the opposite direction
            remainder = fill.quantity - position.quantity
            if remainder > 0.0001:
                fill_side = Side.BUY if fill.side == "BUY" else Side.SELL
                new_fill = Fill(
                    order_id=fill.order_id,
                    symbol=fill.symbol,
                    side=fill.side,
                    quantity=remainder,
                    price=fill.price,
                    expected_price=fill.expected_price,
                )
                self._open_position(new_fill, fill_side)
        else:
            # Partial close
            pnl = position.reduce(fill.quantity, fill.price)
            self._event_store.append(PositionUpdated(
                symbol=fill.symbol,
                quantity=position.quantity,
                entry_price=position.entry_price,
                unrealized_pnl=position.unrealized_pnl,
            ))
