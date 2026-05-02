"""Portfolio performance metrics — Sharpe, drawdown, win rate, etc."""
from __future__ import annotations
import math
from dataclasses import dataclass
from models.events import PositionClosed

@dataclass
class PerformanceMetrics:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    avg_trade_pnl: float
    largest_win: float
    largest_loss: float

def calculate_metrics(events: list, equity_curve: list[float] | None = None) -> PerformanceMetrics:
    """Calculate performance metrics from position close events."""
    closes = [e for e in events if isinstance(e, PositionClosed)]

    if not closes:
        return PerformanceMetrics(0,0,0,0,0,0,0,0,0,0,0,0,0)

    pnls = [e.realized_pnl for e in closes]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    total = len(pnls)
    win_count = len(wins)
    loss_count = len(losses)

    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    total_wins = sum(wins)
    total_losses = abs(sum(losses))

    # Sharpe (annualized, assuming daily returns)
    mean_pnl = sum(pnls) / len(pnls)
    if len(pnls) > 1:
        std_pnl = (sum((p - mean_pnl)**2 for p in pnls) / (len(pnls) - 1)) ** 0.5
        sharpe = (mean_pnl / std_pnl * math.sqrt(252)) if std_pnl > 0 else 0
    else:
        sharpe = 0

    # Max drawdown from equity curve or cumulative P&L
    if equity_curve and len(equity_curve) > 1:
        peak = equity_curve[0]
        max_dd = 0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
    else:
        cum = 0
        peak = 0
        max_dd = 0
        for p in pnls:
            cum += p
            if cum > peak:
                peak = cum
            dd = (peak - cum) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

    return PerformanceMetrics(
        total_trades=total,
        winning_trades=win_count,
        losing_trades=loss_count,
        win_rate=win_count / total if total else 0,
        total_pnl=sum(pnls),
        avg_win=round(avg_win, 2),
        avg_loss=round(avg_loss, 2),
        profit_factor=round(total_wins / total_losses, 2) if total_losses > 0 else float('inf'),
        max_drawdown=round(max_dd, 4),
        sharpe_ratio=round(sharpe, 2),
        avg_trade_pnl=round(mean_pnl, 2),
        largest_win=round(max(pnls), 2) if pnls else 0,
        largest_loss=round(min(pnls), 2) if pnls else 0,
    )
