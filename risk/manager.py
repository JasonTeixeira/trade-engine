"""
Pre-trade risk management.

The RiskManager sits between signals and order submission.
It enforces position limits, drawdown stops, and daily loss limits
before any order reaches the broker.

Think of it as the adult in the room — your strategy says "BUY 100",
the risk manager says "your max is 5 based on current exposure."
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from models.orders import Side
from models.signals import Signal


@dataclass
class RiskCheck:
    """Result of a pre-trade risk check."""
    approved: bool
    adjusted_quantity: float
    reason: str = ""


class RiskManager:
    """
    Pre-trade risk enforcement.

    Checks run in order. If any check rejects, the order is rejected.
    If a check reduces quantity, subsequent checks use the reduced quantity.
    """

    def __init__(
        self,
        max_position_pct: float = 0.05,
        max_drawdown_pct: float = 0.10,
        max_daily_loss_pct: float = 0.02,
        max_positions: int = 10,
        max_correlation: float = 0.80,
        initial_capital: float = 100_000,
    ):
        self.max_position_pct = max_position_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_positions = max_positions
        # NOTE: Correlation checking not yet implemented — requires price history for correlation matrix
        self.max_correlation = max_correlation

        # Track daily P&L
        self._daily_pnl: float = 0.0
        self._peak_equity: float = initial_capital
        self._trading_halted: bool = False
        self._halt_reason: str = ""

    def check_signal(
        self,
        signal: Signal,
        account_equity: float,
        current_positions: dict,
        current_price: float,
    ) -> RiskCheck:
        """
        Run all risk checks against a signal.

        Returns a RiskCheck with approved/rejected status and
        potentially adjusted quantity.
        """
        # Check 1: Is trading halted?
        if self._trading_halted:
            return RiskCheck(
                approved=False,
                adjusted_quantity=0,
                reason=f"Trading halted: {self._halt_reason}"
            )

        # Check 2: Max drawdown
        drawdown = self._calculate_drawdown(account_equity)
        if drawdown > self.max_drawdown_pct:
            self._halt_trading(f"Max drawdown exceeded: {drawdown:.1%} > {self.max_drawdown_pct:.1%}")
            return RiskCheck(
                approved=False,
                adjusted_quantity=0,
                reason=f"Drawdown limit exceeded ({drawdown:.1%})"
            )

        # Check 3: Daily loss limit
        if self._daily_pnl < -(account_equity * self.max_daily_loss_pct):
            self._halt_trading(f"Daily loss limit: ${self._daily_pnl:.2f}")
            return RiskCheck(
                approved=False,
                adjusted_quantity=0,
                reason=f"Daily loss limit exceeded (${self._daily_pnl:.2f})"
            )

        # Check 4: Max positions (only for new positions)
        symbol = signal.symbol
        if symbol not in current_positions and len(current_positions) >= self.max_positions:
            return RiskCheck(
                approved=False,
                adjusted_quantity=0,
                reason=f"Max positions reached ({self.max_positions})"
            )

        # Check 5: Position sizing
        max_notional = account_equity * self.max_position_pct
        max_quantity = max_notional / current_price if current_price > 0 else 0

        # Scale by signal strength
        target_quantity = max_quantity * signal.strength

        if target_quantity < 0.01:
            return RiskCheck(
                approved=False,
                adjusted_quantity=0,
                reason="Calculated quantity too small after risk sizing"
            )

        return RiskCheck(
            approved=True,
            adjusted_quantity=round(target_quantity, 4),
            reason="Approved"
        )

    def update_daily_pnl(self, pnl_change: float) -> None:
        """Update the running daily P&L."""
        self._daily_pnl += pnl_change

    def update_equity(self, equity: float) -> None:
        """Update peak equity for drawdown calculation."""
        if equity > self._peak_equity:
            self._peak_equity = equity

    def reset_daily(self) -> None:
        """Reset daily counters (call at start of each trading day)."""
        self._daily_pnl = 0.0
        self._trading_halted = False
        self._halt_reason = ""

    @property
    def is_halted(self) -> bool:
        return self._trading_halted

    @property
    def halt_reason(self) -> str:
        return self._halt_reason

    @property
    def daily_pnl(self) -> float:
        return self._daily_pnl

    def _calculate_drawdown(self, current_equity: float) -> float:
        """Calculate current drawdown from peak equity."""
        if self._peak_equity <= 0:
            return 0.0
        return (self._peak_equity - current_equity) / self._peak_equity

    def _halt_trading(self, reason: str) -> None:
        """Halt all trading with a reason."""
        self._trading_halted = True
        self._halt_reason = reason
