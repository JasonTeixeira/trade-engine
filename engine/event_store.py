"""
Append-only event store for order and position events.

All events are immutable and timestamped. The store supports
querying by order ID, symbol, time range, and event type.
This enables full audit trail reconstruction and event replay.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, Type
from models.events import Event


class EventStore:
    """
    In-memory append-only event log.

    Events cannot be modified or deleted once stored.
    For production, this would be backed by a database or
    message queue (Kafka, EventStoreDB, PostgreSQL).
    """

    def __init__(self):
        self._events: list[Event] = []
        self._by_order: dict[str, list[Event]] = {}
        self._by_symbol: dict[str, list[Event]] = {}

    def append(self, event: Event) -> None:
        """Store an event. Events are immutable once stored."""
        self._events.append(event)
        if hasattr(event, 'order_id') and event.order_id:
            self._by_order.setdefault(event.order_id, []).append(event)
        if hasattr(event, 'symbol') and event.symbol:
            self._by_symbol.setdefault(event.symbol, []).append(event)

    @property
    def count(self) -> int:
        """Total number of events stored."""
        return len(self._events)

    def get_all(self) -> list[Event]:
        """Return all events in chronological order."""
        return list(self._events)

    def get_by_order(self, order_id: str) -> list[Event]:
        """Return all events for a specific order."""
        return list(self._by_order.get(order_id, []))

    def get_by_symbol(self, symbol: str) -> list[Event]:
        """Return all events for a specific symbol."""
        return list(self._by_symbol.get(symbol, []))

    def get_by_type(self, event_type: Type[Event]) -> list[Event]:
        """Return all events of a specific type."""
        return [e for e in self._events if isinstance(e, event_type)]

    def get_since(self, since: datetime) -> list[Event]:
        """Return all events after the given timestamp."""
        return [e for e in self._events if e.timestamp >= since]

    def get_between(self, start: datetime, end: datetime) -> list[Event]:
        """Return events within a time range."""
        return [
            e for e in self._events
            if start <= e.timestamp <= end
        ]

    def __len__(self) -> int:
        return self.count

    def __repr__(self) -> str:
        return f"EventStore(events={self.count})"
