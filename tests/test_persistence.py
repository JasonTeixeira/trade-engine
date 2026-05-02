"""Tests for persistent event store and new engine features."""
import os
import tempfile
from models.orders import Side
from models.signals import Signal
from engine.core import Engine
from engine.brokers import SimulatedBroker
from engine.metrics import calculate_metrics
from engine.export import export_trades_csv, export_events_csv
from risk.manager import RiskManager


class TestPersistentStore:
    def setup_method(self):
        self.db_file = tempfile.mktemp(suffix=".db")
        self.broker = SimulatedBroker(initial_capital=100_000, seed=42)
        self.risk = RiskManager(max_position_pct=0.10)
        self.engine = Engine(self.broker, self.risk, persist=True, db_path=self.db_file)

    def teardown_method(self):
        if hasattr(self.engine, '_event_store') and hasattr(self.engine._event_store, 'close'):
            self.engine._event_store.close()
        if os.path.exists(self.db_file):
            os.remove(self.db_file)

    def test_events_persist_to_sqlite(self):
        signal = Signal(symbol="ES", side=Side.BUY, strength=0.8)
        self.engine.submit_signal(signal, current_price=5000.0)
        events = self.engine.get_events()
        assert len(events) > 0

    def test_events_survive_reload(self):
        signal = Signal(symbol="NQ", side=Side.BUY, strength=0.7)
        self.engine.submit_signal(signal, current_price=18000.0)
        event_count = len(self.engine.get_events())
        self.engine._event_store.close()

        # Reload from same DB
        from engine.persistent_store import PersistentEventStore
        store2 = PersistentEventStore(self.db_file)
        assert store2.count == event_count
        store2.close()

    def test_persist_false_uses_memory(self):
        engine = Engine(
            SimulatedBroker(initial_capital=50_000),
            RiskManager(),
            persist=False,
        )
        from engine.event_store import EventStore
        assert isinstance(engine._event_store, EventStore)


class TestMetrics:
    def setup_method(self):
        self.broker = SimulatedBroker(initial_capital=100_000, seed=42)
        self.risk = RiskManager(max_position_pct=0.10)
        self.engine = Engine(self.broker, self.risk)

    def test_performance_returns_metrics(self):
        # Execute some trades
        for price in [5000, 5050, 5100]:
            signal = Signal(symbol="ES", side=Side.BUY, strength=0.5)
            self.engine.submit_signal(signal, current_price=price)

        metrics = self.engine.performance()
        assert metrics.total_trades >= 0
        assert hasattr(metrics, 'sharpe_ratio')
        assert hasattr(metrics, 'win_rate')
        assert hasattr(metrics, 'max_drawdown')

    def test_metrics_with_closed_positions(self):
        # Open and close a position
        self.engine.submit_signal(
            Signal(symbol="NQ", side=Side.BUY, strength=0.8),
            current_price=18000.0,
        )
        self.engine.close_position("NQ", current_price=18100.0)

        metrics = self.engine.performance()
        assert metrics.total_trades == 1
        assert metrics.total_pnl != 0

    def test_calculate_metrics_empty(self):
        metrics = calculate_metrics([])
        assert metrics.total_trades == 0
        assert metrics.win_rate == 0


class TestExport:
    def setup_method(self):
        self.broker = SimulatedBroker(initial_capital=100_000, seed=42)
        self.risk = RiskManager(max_position_pct=0.10)
        self.engine = Engine(self.broker, self.risk)
        self.tmpdir = tempfile.mkdtemp()

    def test_export_trades_csv(self):
        self.engine.submit_signal(
            Signal(symbol="CL", side=Side.BUY, strength=0.6),
            current_price=80.0,
        )
        self.engine.close_position("CL", current_price=82.0)

        filepath = self.engine.export_trades(f"{self.tmpdir}/trades.csv")
        assert os.path.exists(filepath)
        with open(filepath) as f:
            lines = f.readlines()
        assert len(lines) >= 2  # header + at least 1 trade

    def test_export_events_csv(self):
        self.engine.submit_signal(
            Signal(symbol="GC", side=Side.BUY, strength=0.5),
            current_price=2300.0,
        )
        filepath = self.engine.export_events(f"{self.tmpdir}/events.csv")
        assert os.path.exists(filepath)
        with open(filepath) as f:
            lines = f.readlines()
        assert len(lines) >= 2  # header + events


class TestTimezoneAwareness:
    def test_events_have_timezone(self):
        from models.events import OrderCreated
        event = OrderCreated(order_id="test", symbol="ES", side="BUY", quantity=1)
        assert event.timestamp.tzinfo is not None

    def test_orders_have_timezone(self):
        from models.orders import Order, Side
        order = Order(symbol="ES", side=Side.BUY, quantity=1)
        assert order.created_at.tzinfo is not None
