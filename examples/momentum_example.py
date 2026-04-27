"""
Example: Running a momentum strategy through the trade engine.

Simulates 100 bars of price data and runs the momentum strategy,
demonstrating the full signal → risk → order → fill → position flow.
"""

import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.core import Engine
from engine.brokers import SimulatedBroker
from risk.manager import RiskManager
from strategies.momentum import MomentumStrategy


def generate_price_series(start: float, n: int, volatility: float = 0.02, seed: int = 42) -> list[float]:
    """Generate a random walk price series with upward drift."""
    rng = random.Random(seed)
    prices = [start]
    for _ in range(n - 1):
        change = rng.gauss(0.0003, volatility)  # Slight upward drift
        prices.append(prices[-1] * (1 + change))
    return prices


def main():
    # Initialize engine
    broker = SimulatedBroker(
        initial_capital=100_000,
        slippage_bps=5,
        commission_per_trade=4.50,
        seed=42,
    )

    risk_manager = RiskManager(
        max_position_pct=0.10,
        max_drawdown_pct=0.15,
        max_daily_loss_pct=0.03,
        max_positions=5,
    )
    risk_manager.update_equity(100_000)

    engine = Engine(broker=broker, risk_manager=risk_manager)
    strategy = MomentumStrategy(symbol="ES", lookback=20, entry_threshold=0.01)

    # Simulate 100 bars
    prices = generate_price_series(4500.0, 100)

    print("=" * 60)
    print("  Trade Engine — Momentum Strategy Example")
    print("=" * 60)
    print(f"  Initial Capital: ${broker.initial_capital:,.2f}")
    print(f"  Symbol: ES | Lookback: 20 | Threshold: 1%")
    print(f"  Risk: 10% max position, 15% max drawdown")
    print("=" * 60)
    print()

    for i, price in enumerate(prices):
        bar = {"close": price, "high": price * 1.002, "low": price * 0.998, "volume": 50000}

        # Update engine price
        engine.update_price("ES", price)

        # Get strategy signal
        positions = engine.get_all_positions()
        signal = strategy.on_bar(bar, positions)

        if signal:
            order = engine.submit_signal(signal, current_price=price)
            if order and order.state.value == "FILLED":
                print(f"  Bar {i:3d} | Price: {price:8.2f} | {signal.side.value:4s} {order.filled_quantity:.2f} @ {order.average_fill_price:.2f}")
            elif order and order.state.value == "REJECTED":
                print(f"  Bar {i:3d} | Price: {price:8.2f} | REJECTED: {order.rejection_reason}")

    # Final summary
    summary = engine.portfolio_summary()
    print()
    print("=" * 60)
    print("  Results")
    print("=" * 60)
    print(f"  Final Equity:    ${summary.equity:>12,.2f}")
    print(f"  Return:          {broker.return_pct:>12.2%}")
    print(f"  Unrealized P&L:  ${summary.unrealized_pnl:>12,.2f}")
    print(f"  Realized P&L:    ${summary.realized_pnl:>12,.2f}")
    print(f"  Total P&L:       ${summary.total_pnl:>12,.2f}")
    print(f"  Open Positions:  {summary.open_positions:>12d}")
    print(f"  Total Orders:    {summary.total_orders:>12d}")
    print(f"  Total Events:    {summary.total_events:>12d}")
    print(f"  Trading Halted:  {'YES' if summary.is_halted else 'NO':>12s}")
    print("=" * 60)

    # Show event log for last order
    if summary.total_orders > 0:
        print()
        print("  Event Log (last order):")
        all_events = engine.get_events()
        for event in all_events[-5:]:
            print(f"    {type(event).__name__}: {event}")


if __name__ == "__main__":
    main()
