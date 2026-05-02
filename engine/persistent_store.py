"""SQLite-backed event store for production persistence."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from models.events import (Event, OrderCreated, OrderSubmitted, OrderRejected,
                           OrderFilled, OrderPartialFill, OrderCancelled,
                           PositionOpened, PositionClosed, PositionUpdated)

EVENT_CLASSES = {
    "OrderCreated": OrderCreated,
    "OrderSubmitted": OrderSubmitted,
    "OrderRejected": OrderRejected,
    "OrderFilled": OrderFilled,
    "OrderPartialFill": OrderPartialFill,
    "OrderCancelled": OrderCancelled,
    "PositionOpened": PositionOpened,
    "PositionClosed": PositionClosed,
    "PositionUpdated": PositionUpdated,
}

class PersistentEventStore:
    """SQLite-backed append-only event store that survives restarts."""

    def __init__(self, db_path: str = "data/trade_engine.db"):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._create_tables()
        self._events: list[Event] = []
        self._load_events()

    def _create_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                data TEXT NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)
        """)
        self._conn.commit()

    def _load_events(self):
        """Load all events from SQLite on startup."""
        cursor = self._conn.execute("SELECT event_type, data FROM events ORDER BY id")
        for event_type, data_json in cursor:
            cls = EVENT_CLASSES.get(event_type)
            if cls:
                data = json.loads(data_json)
                # Convert timestamp string back to datetime
                if "timestamp" in data:
                    data["timestamp"] = datetime.fromisoformat(data["timestamp"])
                self._events.append(cls(**data))

    def append(self, event: Event) -> None:
        """Store an event in memory and SQLite."""
        self._events.append(event)
        event_type = type(event).__name__
        data = {}
        for field_name in event.__dataclass_fields__:
            val = getattr(event, field_name)
            if isinstance(val, datetime):
                val = val.isoformat()
            data[field_name] = val
        self._conn.execute(
            "INSERT INTO events (event_id, event_type, timestamp, data) VALUES (?, ?, ?, ?)",
            (event.event_id, event_type, event.timestamp.isoformat(), json.dumps(data))
        )
        # Don't commit here — call flush() when done for better performance

    def flush(self):
        """Commit all pending events to disk."""
        self._conn.commit()

    def __del__(self):
        try:
            self.flush()
        except Exception:
            pass

    @property
    def count(self) -> int:
        return len(self._events)

    def get_all(self) -> list[Event]:
        return list(self._events)

    def get_by_order(self, order_id: str) -> list[Event]:
        return [e for e in self._events if hasattr(e, 'order_id') and e.order_id == order_id]

    def get_by_symbol(self, symbol: str) -> list[Event]:
        return [e for e in self._events if hasattr(e, 'symbol') and e.symbol == symbol]

    def get_by_type(self, event_type) -> list[Event]:
        return [e for e in self._events if isinstance(e, event_type)]

    def get_since(self, since: datetime) -> list[Event]:
        return [e for e in self._events if e.timestamp >= since]

    def __len__(self) -> int:
        return self.count

    def close(self):
        self._conn.close()
