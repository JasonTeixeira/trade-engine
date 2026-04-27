"""
Fill model — represents a single execution from a broker.

Fills are immutable records of what actually happened in the market.
They include slippage (difference between expected and actual price).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


@dataclass(frozen=True)
class Fill:
    """
    An immutable record of a trade execution.

    Fills come from the broker and represent what actually happened —
    not what was requested. The slippage field captures the difference.
    """
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    expected_price: float
    commission: float = 0.0
    fill_id: str = field(default_factory=lambda: f"FILL-{uuid4().hex[:8].upper()}")
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def slippage(self) -> float:
        """Price slippage (actual - expected). Positive = worse fill."""
        return abs(self.price - self.expected_price)

    @property
    def slippage_bps(self) -> float:
        """Slippage in basis points."""
        if self.expected_price == 0:
            return 0.0
        return (self.slippage / self.expected_price) * 10_000

    @property
    def total_cost(self) -> float:
        """Total cost including commission."""
        return (self.price * self.quantity) + self.commission

    def __repr__(self) -> str:
        return (
            f"Fill({self.side} {self.quantity} {self.symbol} "
            f"@ {self.price:.2f}, slippage={self.slippage_bps:.1f}bps)"
        )
