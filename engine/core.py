"""
Core trading engine — orchestrates order management, position tracking,
risk management, and event sourcing.

This is the central coordinator. Strategies submit signals, the engine
validates them through the risk manager, converts them to orders,
routes them to the broker, and updates positions based on fills.

Usage:
    broker = SimulatedBroker(initial_capital=100_000)
    risk = RiskManager(max_position_pct=0.05)
    engine = Engine(broker=broker, risk_manager=risk)

    signal = Signal(symbol="ES", side=Side.BUY, strength=0.8)
    order = engine.submit_signal(signal, current_price=4521.25)

    print(engine.get_position("ES"))
    print(engine.portfolio_summary())
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from models.orders import Order, OrderState, Side
from models.signals import Signal
from models.positions import Position
from engine.order_manager import OrderManager
from engine.position_tracker import PositionTracker
from engine.event_store import EventStore
from engine.brokers import Broker
from engine.logging import logger
from risk.manager import RiskManager


@dataclass
class PortfolioSummary:
    """Snapshot of portfolio state."""
    equity: float
    open_positions: int
    total_orders: int
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    total_events: int
    is_halted: bool
    halt_reason: str


class Engine:
    """
    Core trading engine.

    Orchestrates: Signal → Risk Check → Order → Broker → Fill → Position → P&L

    All state changes are captured as events in the event store
    for full audit trail and replay capability.
    """

    def __init__(self, broker: Broker, risk_manager: RiskManager, persist: bool = False, db_path: str = "data/trade_engine.db"):
        if persist:
            from engine.persistent_store import PersistentEventStore
            self._event_store = PersistentEventStore(db_path)
        else:
            self._event_store = EventStore()
        self._order_manager = OrderManager(self._event_store)
        self._position_tracker = PositionTracker(self._event_store)
        self._broker = broker
        self._risk_manager = risk_manager
        self._prices: dict[str, float] = {}

    def submit_signal(
        self,
        signal: Signal,
        current_price: Optional[float] = None,
    ) -> Optional[Order]:
        """
        Submit a trading signal to the engine.

        The signal goes through risk checks, gets converted to a sized
        order, and is routed to the broker for execution.

        Returns the Order if created, None if rejected by risk.
        """
        logger.info(f"Signal received: {signal.side.value} {signal.symbol} strength={signal.strength}")

        price = current_price or self._prices.get(signal.symbol, 0)
        if price <= 0:
            raise ValueError(f"No price available for {signal.symbol}")

        # Update stored price
        self._prices[signal.symbol] = price

        # Risk check
        positions = self._position_tracker.get_all_positions()
        check = self._risk_manager.check_signal(
            signal=signal,
            account_equity=self._broker.equity,
            current_positions=positions,
            current_price=price,
        )

        logger.info(f"Risk check: approved={check.approved}, reason={check.reason}")

        if not check.approved:
            # Create and immediately reject the order
            order = self._order_manager.create_order(
                symbol=signal.symbol,
                side=signal.side,
                quantity=0,
                strategy_id=signal.strategy_id,
            )
            self._order_manager.reject(order.order_id, check.reason)
            return order

        # Create order with risk-adjusted quantity
        order = self._order_manager.create_order(
            symbol=signal.symbol,
            side=signal.side,
            quantity=check.adjusted_quantity,
            strategy_id=signal.strategy_id,
        )

        logger.info(f"Order created: {order.order_id} {order.side.value} {order.quantity} {order.symbol}")

        # Submit to broker
        self._order_manager.submit(order.order_id, self._broker.name)

        fill = self._broker.submit_order(order, price)

        if fill is None:
            self._order_manager.reject(order.order_id, "Broker rejected order")
            return order

        # Apply fill
        self._order_manager.apply_fill(order.order_id, fill)
        self._position_tracker.apply_fill(fill)

        logger.info(f"Fill applied: {fill.quantity} @ {fill.price} (slippage={fill.slippage_bps:.1f}bps)")

        # Update risk manager
        self._risk_manager.update_equity(self._broker.equity)

        return order

    def close_position(
        self,
        symbol: str,
        current_price: Optional[float] = None,
    ) -> Optional[Order]:
        """
        Close an open position by submitting an opposite-side signal.

        Note: Close orders intentionally bypass risk checks. This is by design —
        we always want to be able to exit a position regardless of drawdown or
        daily loss limits. The broker still validates sufficient capital for the
        opposite-side order.
        """
        logger.info(f"Closing position: {symbol}")
        position = self._position_tracker.get_position(symbol)
        if not position:
            raise ValueError(f"No open position for {symbol}")

        price = current_price or self._prices.get(symbol, 0)

        # Create opposite-side order for the full position quantity
        close_side = Side.SELL if position.side == Side.BUY else Side.BUY

        order = self._order_manager.create_order(
            symbol=symbol,
            side=close_side,
            quantity=position.quantity,
        )

        self._order_manager.submit(order.order_id, self._broker.name)
        fill = self._broker.submit_order(order, price)

        if fill is None:
            self._order_manager.reject(order.order_id, "Broker rejected close order")
            return order

        self._order_manager.apply_fill(order.order_id, fill)
        self._position_tracker.apply_fill(fill)

        # Update daily P&L in risk manager
        self._risk_manager.update_daily_pnl(position.realized_pnl)
        self._risk_manager.update_equity(self._broker.equity)

        return order

    def update_price(self, symbol: str, price: float) -> None:
        """Update market price for a symbol."""
        logger.debug(f"Price update: {symbol} = {price}")
        self._prices[symbol] = price
        self._position_tracker.update_price(symbol, price)
        # Update broker with mark-to-market value
        if hasattr(self._broker, 'update_positions_value'):
            self._broker.update_positions_value(self._position_tracker.total_unrealized_pnl)

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get the current position for a symbol."""
        return self._position_tracker.get_position(symbol)

    def get_all_positions(self) -> dict[str, Position]:
        """Get all open positions."""
        return self._position_tracker.get_all_positions()

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID."""
        return self._order_manager.get_order(order_id)

    def get_events(self, order_id: Optional[str] = None):
        """Get events, optionally filtered by order ID."""
        if order_id:
            return self._event_store.get_by_order(order_id)
        return self._event_store.get_all()

    def portfolio_summary(self) -> PortfolioSummary:
        """Get a snapshot of the current portfolio state."""
        return PortfolioSummary(
            equity=self._broker.equity,
            open_positions=self._position_tracker.open_position_count,
            total_orders=self._order_manager.total_orders,
            unrealized_pnl=self._position_tracker.total_unrealized_pnl,
            realized_pnl=self._position_tracker.total_realized_pnl,
            total_pnl=self._position_tracker.total_pnl,
            total_events=len(self._event_store),
            is_halted=self._risk_manager.is_halted,
            halt_reason=self._risk_manager.halt_reason,
        )

    def performance(self) -> 'PerformanceMetrics':
        """Calculate portfolio performance metrics."""
        from engine.metrics import calculate_metrics
        return calculate_metrics(self._event_store.get_all())

    def flush(self) -> None:
        """Flush pending events to disk (for persistent stores)."""
        if hasattr(self._event_store, 'flush'):
            self._event_store.flush()

    def export_trades(self, filepath: str = "data/trades.csv") -> str:
        """Export trade history to CSV (compatible with Nexural Research)."""
        from engine.export import export_trades_csv
        return export_trades_csv(self._event_store.get_all(), filepath)

    def export_events(self, filepath: str = "data/events.csv") -> str:
        """Export full event audit trail to CSV."""
        from engine.export import export_events_csv
        return export_events_csv(self._event_store.get_all(), filepath)
