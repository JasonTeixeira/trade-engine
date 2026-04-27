"""
Integration tests for the core trading engine.

Tests the full flow: Signal → Risk → Order → Broker → Fill → Position → P&L
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.core import Engine
from engine.brokers import SimulatedBroker
from risk.manager import RiskManager
from models.orders import Side, OrderState
from models.signals import Signal
from models.events import OrderCreated, OrderFilled, PositionOpened


class TestEngineBasicFlow:
    def setup_method(self):
        self.broker = SimulatedBroker(initial_capital=100_000, slippage_bps=0, seed=42)
        self.risk = RiskManager(max_position_pct=0.10, max_drawdown_pct=0.20)
        self.risk.update_equity(100_000)
        self.engine = Engine(broker=self.broker, risk_manager=self.risk)

    def test_submit_buy_signal_creates_position(self):
        signal = Signal(symbol="ES", side=Side.BUY, strength=0.5)
        order = self.engine.submit_signal(signal, current_price=4500.0)

        assert order is not None
        assert order.state == OrderState.FILLED

        position = self.engine.get_position("ES")
        assert position is not None
        assert position.side == Side.BUY
        assert position.quantity > 0

    def test_close_position(self):
        # Open
        signal = Signal(symbol="ES", side=Side.BUY, strength=0.5)
        self.engine.submit_signal(signal, current_price=4500.0)
        pos_before = self.engine.get_position("ES")
        assert pos_before is not None
        assert pos_before.side == Side.BUY

        # Close — should realize P&L
        self.engine.close_position("ES", current_price=4510.0)
        summary = self.engine.portfolio_summary()
        # Position should be closed (realized P&L from closed positions list)
        assert summary.total_orders == 2  # Open + close

    def test_pnl_calculation_long(self):
        signal = Signal(symbol="ES", side=Side.BUY, strength=0.5)
        self.engine.submit_signal(signal, current_price=100.0)

        # Price goes up
        self.engine.update_price("ES", 110.0)
        position = self.engine.get_position("ES")
        assert position.unrealized_pnl > 0

    def test_pnl_calculation_after_close(self):
        signal = Signal(symbol="ES", side=Side.BUY, strength=0.5)
        self.engine.submit_signal(signal, current_price=100.0)

        self.engine.close_position("ES", current_price=110.0)
        summary = self.engine.portfolio_summary()
        assert summary.realized_pnl > 0

    def test_event_sourcing(self):
        signal = Signal(symbol="ES", side=Side.BUY, strength=0.5)
        order = self.engine.submit_signal(signal, current_price=4500.0)

        events = self.engine.get_events(order_id=order.order_id)
        event_types = [type(e).__name__ for e in events]

        assert "OrderCreated" in event_types
        assert "OrderSubmitted" in event_types
        assert "OrderFilled" in event_types

    def test_all_events_have_timestamps(self):
        signal = Signal(symbol="ES", side=Side.BUY, strength=0.5)
        self.engine.submit_signal(signal, current_price=4500.0)

        for event in self.engine.get_events():
            assert event.timestamp is not None

    def test_portfolio_summary(self):
        signal = Signal(symbol="ES", side=Side.BUY, strength=0.5)
        self.engine.submit_signal(signal, current_price=4500.0)

        summary = self.engine.portfolio_summary()
        assert summary.open_positions == 1
        assert summary.total_orders == 1
        assert summary.total_events > 0
        assert not summary.is_halted


class TestRiskManagement:
    def setup_method(self):
        self.broker = SimulatedBroker(initial_capital=100_000, slippage_bps=0, seed=42)
        self.risk = RiskManager(
            max_position_pct=0.05,
            max_drawdown_pct=0.10,
            max_daily_loss_pct=0.02,
            max_positions=3,
        )
        self.risk.update_equity(100_000)
        self.engine = Engine(broker=self.broker, risk_manager=self.risk)

    def test_position_size_limited_by_risk(self):
        signal = Signal(symbol="ES", side=Side.BUY, strength=1.0)
        order = self.engine.submit_signal(signal, current_price=100.0)

        # Max position = 5% of 100K = $5,000 notional
        # At $100/unit, max quantity = 50
        position = self.engine.get_position("ES")
        assert position.quantity <= 50.0

    def test_signal_strength_scales_position(self):
        # Strength 0.5 should give roughly half the max position
        signal_half = Signal(symbol="ES", side=Side.BUY, strength=0.5)
        order = self.engine.submit_signal(signal_half, current_price=100.0)
        pos = self.engine.get_position("ES")
        half_qty = pos.quantity

        # Reset
        self.engine.close_position("ES", current_price=100.0)

        # Strength 1.0 should give full max position
        signal_full = Signal(symbol="NQ", side=Side.BUY, strength=1.0)
        order = self.engine.submit_signal(signal_full, current_price=100.0)
        pos = self.engine.get_position("NQ")
        full_qty = pos.quantity

        assert full_qty > half_qty

    def test_max_positions_enforced(self):
        for symbol in ["ES", "NQ", "CL"]:
            signal = Signal(symbol=symbol, side=Side.BUY, strength=0.5)
            self.engine.submit_signal(signal, current_price=100.0)

        # 4th position should be rejected
        signal = Signal(symbol="GC", side=Side.BUY, strength=0.5)
        order = self.engine.submit_signal(signal, current_price=100.0)
        assert order.state == OrderState.REJECTED

    def test_drawdown_halts_trading(self):
        self.risk.update_equity(100_000)  # Set peak

        # Simulate 15% drawdown (exceeds 10% limit)
        self.broker.capital = 85_000

        signal = Signal(symbol="ES", side=Side.BUY, strength=0.5)
        order = self.engine.submit_signal(signal, current_price=100.0)
        assert order.state == OrderState.REJECTED
        assert self.risk.is_halted


class TestSimulatedBroker:
    def test_slippage_applied(self):
        broker = SimulatedBroker(slippage_bps=10, seed=42)
        from models.orders import Order
        order = Order(symbol="ES", side=Side.BUY, quantity=1.0)
        order.transition_to(OrderState.PENDING)
        order.transition_to(OrderState.SUBMITTED)

        fill = broker.submit_order(order, current_price=100.0)
        assert fill is not None
        # Buy should fill above 100 (positive slippage)
        assert fill.price > 100.0
        assert fill.slippage_bps > 0

    def test_sell_slippage_direction(self):
        broker = SimulatedBroker(slippage_bps=10, seed=42)
        from models.orders import Order
        order = Order(symbol="ES", side=Side.SELL, quantity=1.0)
        order.transition_to(OrderState.PENDING)
        order.transition_to(OrderState.SUBMITTED)

        fill = broker.submit_order(order, current_price=100.0)
        assert fill is not None
        # Sell should fill below 100
        assert fill.price < 100.0

    def test_commission_deducted(self):
        broker = SimulatedBroker(
            initial_capital=100_000,
            commission_per_trade=5.0,
            slippage_bps=0,
            seed=42,
        )
        from models.orders import Order
        order = Order(symbol="ES", side=Side.BUY, quantity=1.0)
        order.transition_to(OrderState.PENDING)
        order.transition_to(OrderState.SUBMITTED)

        fill = broker.submit_order(order, current_price=100.0)
        # Capital should be reduced by (price * qty) + commission
        assert broker.capital < 100_000
        assert fill.commission == 5.0
