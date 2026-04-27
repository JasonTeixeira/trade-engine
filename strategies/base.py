"""Abstract strategy interface."""

from abc import ABC, abstractmethod
from typing import Optional
from models.signals import Signal


class Strategy(ABC):
    """
    Base class for trading strategies.

    Strategies receive market data and return signals.
    They should not manage orders or positions directly —
    that's the engine's job.
    """

    @abstractmethod
    def on_bar(self, bar: dict, positions: dict) -> Optional[Signal]:
        """
        Called on each new bar of market data.

        Args:
            bar: Market data (open, high, low, close, volume)
            positions: Current open positions {symbol: Position}

        Returns:
            Signal if the strategy wants to trade, None otherwise.
        """
        pass

    def on_fill(self, fill) -> None:
        """Called when an order is filled. Override for fill tracking."""
        pass

    def on_reject(self, order) -> None:
        """Called when an order is rejected. Override for logging."""
        pass
