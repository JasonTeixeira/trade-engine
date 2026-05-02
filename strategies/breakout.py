"""
Breakout strategy — buys when price breaks above resistance.

Uses Donchian channels (N-period high/low) to detect breakouts.
The assumption: a new high means buyers are in control and
momentum will continue.

This is the classic trend-following entry — used by the Turtle Traders.
"""

from typing import Optional
from models.signals import Signal
from models.orders import Side
from strategies.base import Strategy


class BreakoutStrategy(Strategy):
    """
    Donchian channel breakout strategy.

    - Enter LONG when price breaks above the N-period high
    - Exit when price drops below the N/2-period low
    - Signal strength based on volume confirmation
    """

    def __init__(
        self,
        symbol: str = "ES",
        entry_lookback: int = 20,
        exit_lookback: int = 10,
        volume_confirm: bool = True,
    ):
        self.symbol = symbol
        self.entry_lookback = entry_lookback
        self.exit_lookback = exit_lookback
        self.volume_confirm = volume_confirm
        self._highs: list[float] = []
        self._lows: list[float] = []
        self._closes: list[float] = []
        self._volumes: list[float] = []

    def on_bar(self, bar: dict, positions: dict) -> Optional[Signal]:
        high = bar.get("high", 0)
        low = bar.get("low", 0)
        close = bar.get("close", 0)
        volume = bar.get("volume", 0)

        if close <= 0:
            return None

        self._highs.append(high)
        self._lows.append(low)
        self._closes.append(close)
        self._volumes.append(volume)

        # Keep only what we need
        max_lookback = max(self.entry_lookback, self.exit_lookback)
        if len(self._closes) > max_lookback * 2:
            trim_to = max_lookback + 2  # +2 to account for excluding current bar
            self._highs = self._highs[-trim_to:]
            self._lows = self._lows[-trim_to:]
            self._closes = self._closes[-trim_to:]
            self._volumes = self._volumes[-trim_to:]

        if len(self._closes) < self.entry_lookback + 1:
            return None

        # Donchian channels (exclude current bar to avoid look-ahead)
        entry_high = max(self._highs[-(self.entry_lookback + 1):-1])
        exit_low = min(self._lows[-(self.exit_lookback + 1):-1])

        has_position = self.symbol in positions

        # Entry: price breaks above the channel high
        if close > entry_high and not has_position:
            # Volume confirmation: current volume > average
            strength = 0.7
            if self.volume_confirm and len(self._volumes) >= 20:
                avg_vol = sum(self._volumes[-20:]) / 20
                if volume > avg_vol * 1.2:
                    strength = 1.0  # Strong breakout with volume
                elif volume < avg_vol * 0.8:
                    strength = 0.3  # Weak breakout, low volume

            return Signal(
                symbol=self.symbol,
                side=Side.BUY,
                strength=strength,
                strategy_id="breakout",
                metadata={
                    "channel_high": entry_high,
                    "channel_low": exit_low,
                    "breakout_amount": close - entry_high,
                },
            )

        # Exit: price drops below the exit channel low
        if close < exit_low and has_position:
            return Signal(
                symbol=self.symbol,
                side=Side.SELL,
                strength=1.0,
                strategy_id="breakout",
                metadata={
                    "exit_low": exit_low,
                    "reason": "channel_exit",
                },
            )

        return None
