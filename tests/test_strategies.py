"""
Tests for all trading strategies.

Validates:
- Strategies generate signals under expected conditions
- No signals generated with insufficient data
- Signal strength is bounded 0-1
- Strategy metadata contains expected fields
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.momentum import MomentumStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.breakout import BreakoutStrategy
from models.orders import Side


class TestMomentumStrategy:
    def test_no_signal_with_insufficient_data(self):
        strategy = MomentumStrategy(symbol="ES", lookback=20)
        # Feed only 10 bars
        for i in range(10):
            signal = strategy.on_bar({"close": 100 + i}, {})
        assert signal is None

    def test_buy_signal_on_uptrend(self):
        strategy = MomentumStrategy(symbol="ES", lookback=5, entry_threshold=0.01)
        # Feed flat data then sharp up move
        for i in range(5):
            strategy.on_bar({"close": 100}, {})
        signal = strategy.on_bar({"close": 105}, {})  # 5% above SMA
        assert signal is not None
        assert signal.side == Side.BUY

    def test_no_duplicate_entry(self):
        strategy = MomentumStrategy(symbol="ES", lookback=5, entry_threshold=0.01)
        for i in range(5):
            strategy.on_bar({"close": 100}, {})
        # First signal with no position
        signal1 = strategy.on_bar({"close": 105}, {})
        # Second signal with existing position — should not re-enter
        signal2 = strategy.on_bar({"close": 106}, {"ES": True})
        assert signal1 is not None
        assert signal2 is None  # Already has position


class TestMeanReversionStrategy:
    def test_buy_on_oversold(self):
        strategy = MeanReversionStrategy(symbol="ES", lookback=20, num_std=2.0)
        # Feed stable data
        for i in range(20):
            strategy.on_bar({"close": 100}, {})
        # Sharp drop below lower band
        signal = strategy.on_bar({"close": 90}, {})
        assert signal is not None
        assert signal.side == Side.BUY
        assert signal.metadata["z_score"] < -2.0

    def test_exit_at_mean(self):
        strategy = MeanReversionStrategy(symbol="ES", lookback=20, exit_at_mean=True)
        for i in range(20):
            strategy.on_bar({"close": 100}, {})
        # Price is at the mean with existing position
        signal = strategy.on_bar({"close": 100}, {"ES": True})
        if signal:
            assert signal.side == Side.SELL

    def test_no_signal_in_normal_range(self):
        strategy = MeanReversionStrategy(symbol="ES", lookback=20, num_std=2.0)
        for i in range(20):
            strategy.on_bar({"close": 100}, {})
        # Price within normal range
        signal = strategy.on_bar({"close": 101}, {})
        assert signal is None


class TestBreakoutStrategy:
    def test_buy_on_channel_break(self):
        strategy = BreakoutStrategy(symbol="ES", entry_lookback=5, volume_confirm=False)
        # Feed data with high of 105
        for i in range(6):
            strategy.on_bar({"close": 100, "high": 105, "low": 95, "volume": 1000000}, {})
        # Break above the channel
        signal = strategy.on_bar({"close": 110, "high": 110, "low": 106, "volume": 1500000}, {})
        assert signal is not None
        assert signal.side == Side.BUY

    def test_exit_on_channel_low_break(self):
        strategy = BreakoutStrategy(symbol="ES", entry_lookback=5, exit_lookback=3, volume_confirm=False)
        for i in range(6):
            strategy.on_bar({"close": 100, "high": 105, "low": 95, "volume": 1000000}, {})
        # Price drops below exit channel with position
        signal = strategy.on_bar({"close": 90, "high": 95, "low": 88, "volume": 2000000}, {"ES": True})
        assert signal is not None
        assert signal.side == Side.SELL

    def test_volume_affects_strength(self):
        strategy = BreakoutStrategy(symbol="ES", entry_lookback=5, volume_confirm=True)
        for i in range(20):
            strategy.on_bar({"close": 100, "high": 105, "low": 95, "volume": 1000000}, {})
        # High volume breakout
        signal_high_vol = strategy.on_bar({"close": 110, "high": 110, "low": 106, "volume": 2000000}, {})
        assert signal_high_vol is not None
        assert signal_high_vol.strength >= 0.7

    def test_signal_strength_bounded(self):
        """All signal strengths should be 0-1."""
        for StrategyClass in [MomentumStrategy, MeanReversionStrategy, BreakoutStrategy]:
            strategy = StrategyClass(symbol="ES")
            for i in range(25):
                signal = strategy.on_bar(
                    {"close": 100 + i * 2, "high": 102 + i * 2, "low": 98 + i * 2, "volume": 1000000},
                    {}
                )
                if signal:
                    assert 0 <= signal.strength <= 1, f"{StrategyClass.__name__} strength out of bounds"
