"""
Trading signals — the interface between strategies and the engine.

A signal represents a trading intention (BUY, SELL, FLAT) with a
strength indicator. The engine's risk manager converts signals
into sized orders.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from models.orders import Side


@dataclass
class Signal:
    """
    A trading signal from a strategy.

    Signals are directional intentions, not orders. The risk manager
    converts signals into appropriately-sized orders based on account
    state, position limits, and drawdown rules.
    """
    symbol: str
    side: Side
    strength: float = 1.0  # 0.0 to 1.0 — used for position sizing
    strategy_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"Signal strength must be 0.0-1.0, got {self.strength}")

    def __repr__(self) -> str:
        return (
            f"Signal({self.side.value} {self.symbol}, "
            f"strength={self.strength:.2f})"
        )
