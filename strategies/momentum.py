"""
Example momentum strategy.

Buys when price is above the N-period moving average by a threshold.
Sells when price drops below the moving average.

This is intentionally simple — the value is in the engine architecture,
not the strategy alpha.
"""

from typing import Optional
from models.signals import Signal
from models.orders import Side
from strategies.base import Strategy


class MomentumStrategy(Strategy):
    """
    Simple moving average crossover momentum strategy.

    - Enter LONG when price > SMA + threshold
    - Exit when price < SMA - threshold
    - Signal strength proportional to distance from SMA
    """

    def __init__(
        self,
        symbol: str = "ES",
        lookback: int = 20,
        entry_threshold: float = 0.01,
        exit_threshold: float = 0.005,
    ):
        self.symbol = symbol
        self.lookback = lookback
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self._prices: list[float] = []

    def on_bar(self, bar: dict, positions: dict) -> Optional[Signal]:
        """Generate signal based on price vs moving average."""
        close = bar.get("close", 0)
        if close <= 0:
            return None

        self._prices.append(close)

        # Keep only what we need
        if len(self._prices) > self.lookback * 2:
            self._prices = self._prices[-self.lookback:]

        # Need enough data for lookback
        if len(self._prices) < self.lookback:
            return None

        # Calculate SMA
        sma = sum(self._prices[-self.lookback:]) / self.lookback
        deviation = (close - sma) / sma

        has_position = self.symbol in positions

        # Entry: price above SMA by threshold
        if deviation > self.entry_threshold and not has_position:
            strength = min(1.0, deviation / (self.entry_threshold * 3))
            return Signal(
                symbol=self.symbol,
                side=Side.BUY,
                strength=strength,
                strategy_id="momentum",
                metadata={"sma": sma, "deviation": deviation},
            )

        # Exit: price below SMA by threshold
        if deviation < -self.exit_threshold and has_position:
            return Signal(
                symbol=self.symbol,
                side=Side.SELL,
                strength=1.0,
                strategy_id="momentum",
                metadata={"sma": sma, "deviation": deviation},
            )

        return None
