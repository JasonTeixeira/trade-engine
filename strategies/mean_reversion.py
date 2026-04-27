"""
Mean-reversion strategy — buys oversold conditions, sells overbought.

Uses Bollinger Bands to detect extreme deviations from the mean.
The assumption: prices that deviate too far from their average
tend to revert. This works best in range-bound markets.

This strategy is the opposite of momentum — it fades moves
rather than following them.
"""

from typing import Optional
from models.signals import Signal
from models.orders import Side
from strategies.base import Strategy


class MeanReversionStrategy(Strategy):
    """
    Bollinger Band mean-reversion strategy.

    - Enter LONG when price drops below lower band (oversold)
    - Enter SHORT when price rises above upper band (overbought)
    - Exit when price returns to the mean (SMA)
    - Signal strength proportional to band deviation
    """

    def __init__(
        self,
        symbol: str = "ES",
        lookback: int = 20,
        num_std: float = 2.0,
        exit_at_mean: bool = True,
    ):
        self.symbol = symbol
        self.lookback = lookback
        self.num_std = num_std
        self.exit_at_mean = exit_at_mean
        self._prices: list[float] = []

    def on_bar(self, bar: dict, positions: dict) -> Optional[Signal]:
        close = bar.get("close", 0)
        if close <= 0:
            return None

        self._prices.append(close)

        if len(self._prices) < self.lookback:
            return None

        window = self._prices[-self.lookback:]
        sma = sum(window) / len(window)
        std = (sum((p - sma) ** 2 for p in window) / len(window)) ** 0.5

        if std == 0:
            return None

        upper_band = sma + self.num_std * std
        lower_band = sma - self.num_std * std
        z_score = (close - sma) / std

        has_position = self.symbol in positions

        # Entry: price below lower band (oversold → buy)
        if close < lower_band and not has_position:
            strength = min(1.0, abs(z_score) / (self.num_std * 1.5))
            return Signal(
                symbol=self.symbol,
                side=Side.BUY,
                strength=strength,
                strategy_id="mean_reversion",
                metadata={"sma": sma, "z_score": z_score, "lower_band": lower_band},
            )

        # Entry: price above upper band (overbought → could short)
        # For simplicity, we only exit existing longs here
        if close > upper_band and has_position:
            return Signal(
                symbol=self.symbol,
                side=Side.SELL,
                strength=1.0,
                strategy_id="mean_reversion",
                metadata={"sma": sma, "z_score": z_score, "upper_band": upper_band},
            )

        # Exit at mean reversion
        if self.exit_at_mean and has_position:
            if abs(z_score) < 0.3:  # Close to the mean
                return Signal(
                    symbol=self.symbol,
                    side=Side.SELL,
                    strength=0.8,
                    strategy_id="mean_reversion",
                    metadata={"sma": sma, "z_score": z_score, "reason": "mean_reversion"},
                )

        return None
