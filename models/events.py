"""
Event sourcing models — every state change is an immutable event.

Events are append-only. They can be replayed to reconstruct any
past state of the system. This is critical for trading systems
where audit trails are a regulatory requirement.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4


@dataclass(frozen=True)
class Event:
    """Base event — all events inherit from this."""
    event_id: str = field(default_factory=lambda: f"EVT-{uuid4().hex[:8].upper()}")
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ═══ Order Events ═══

@dataclass(frozen=True)
class OrderCreated(Event):
    order_id: str = ""
    symbol: str = ""
    side: str = ""
    quantity: float = 0.0
    order_type: str = ""
    limit_price: Optional[float] = None

@dataclass(frozen=True)
class OrderSubmitted(Event):
    order_id: str = ""
    broker: str = ""

@dataclass(frozen=True)
class OrderRejected(Event):
    order_id: str = ""
    reason: str = ""

@dataclass(frozen=True)
class OrderFilled(Event):
    order_id: str = ""
    fill_price: float = 0.0
    quantity: float = 0.0
    slippage_bps: float = 0.0
    commission: float = 0.0

@dataclass(frozen=True)
class OrderPartialFill(Event):
    order_id: str = ""
    fill_price: float = 0.0
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0

@dataclass(frozen=True)
class OrderCancelled(Event):
    order_id: str = ""
    reason: str = ""


# ═══ Position Events ═══

@dataclass(frozen=True)
class PositionOpened(Event):
    symbol: str = ""
    side: str = ""
    quantity: float = 0.0
    entry_price: float = 0.0

@dataclass(frozen=True)
class PositionClosed(Event):
    symbol: str = ""
    realized_pnl: float = 0.0
    hold_duration_seconds: float = 0.0

@dataclass(frozen=True)
class PositionUpdated(Event):
    symbol: str = ""
    quantity: float = 0.0
    entry_price: float = 0.0
    unrealized_pnl: float = 0.0
