"""
Trade Engine API — FastAPI server exposing the trade engine over HTTP.

Provides endpoints for running backtests, querying positions,
metrics, and exporting trade history.
"""

from __future__ import annotations

import sys
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Ensure the project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core import Engine
from engine.brokers import SimulatedBroker
from engine.metrics import calculate_metrics
from risk.manager import RiskManager
from models.signals import Signal
from models.orders import Side
from strategies.momentum import MomentumStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.breakout import BreakoutStrategy

# ── Global state ──────────────────────────────────────────────────────

engine: Engine | None = None

STRATEGIES: dict[str, type] = {
    "momentum": MomentumStrategy,
    "mean_reversion": MeanReversionStrategy,
    "breakout": BreakoutStrategy,
}

# ── App setup ─────────────────────────────────────────────────────────

app = FastAPI(title="Trade Engine API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origin_regex=r"https://.*\.vercel\.app",
)

# ── Pydantic models ──────────────────────────────────────────────────

class RunBacktestRequest(BaseModel):
    strategy: str
    symbol: str = "ES"
    initial_capital: float = 100_000.0
    prices: list[float]
    max_position_pct: float = 0.05
    max_drawdown_pct: float = 0.10
    max_daily_loss_pct: float = 0.02
    max_positions: int = 10


class BacktestResponse(BaseModel):
    total_orders: int
    open_positions: int
    equity: float
    total_pnl: float
    metrics: dict
    orders: list[dict]

# ── Helpers ───────────────────────────────────────────────────────────

def _serialize_event(event) -> dict:
    """Convert a dataclass event to a JSON-safe dict."""
    data = asdict(event)
    for key, value in data.items():
        if isinstance(value, datetime):
            data[key] = value.isoformat()
    data["event_type"] = type(event).__name__
    return data


def _serialize_order(order) -> dict:
    """Convert an Order dataclass to a JSON-safe dict."""
    return {
        "order_id": order.order_id,
        "symbol": order.symbol,
        "side": order.side.value,
        "quantity": order.quantity,
        "filled_quantity": order.filled_quantity,
        "average_fill_price": order.average_fill_price,
        "state": order.state.value,
        "strategy_id": order.strategy_id,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
    }

# ── Endpoints ─────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Health check with available strategies."""
    return {
        "status": "ok",
        "strategies": list(STRATEGIES.keys()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/engine/run", response_model=BacktestResponse)
def run_backtest(req: RunBacktestRequest):
    """Run a backtest with the given strategy and price series."""
    global engine

    if req.strategy not in STRATEGIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy '{req.strategy}'. Available: {list(STRATEGIES.keys())}",
        )

    if len(req.prices) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 price bars")

    # Build engine components
    broker = SimulatedBroker(initial_capital=req.initial_capital, seed=42)
    risk = RiskManager(
        max_position_pct=req.max_position_pct,
        max_drawdown_pct=req.max_drawdown_pct,
        max_daily_loss_pct=req.max_daily_loss_pct,
        max_positions=req.max_positions,
    )
    engine = Engine(broker=broker, risk_manager=risk)

    # Instantiate strategy
    strategy_cls = STRATEGIES[req.strategy]
    strategy = strategy_cls(symbol=req.symbol)

    # Run through price bars
    orders: list[dict] = []
    for i, price in enumerate(req.prices):
        bar = {
            "open": price,
            "high": price * 1.001,
            "low": price * 0.999,
            "close": price,
            "volume": 1000 + i * 10,
        }

        positions = engine.get_all_positions()
        signal = strategy.on_bar(bar, positions)

        if signal is not None:
            order = engine.submit_signal(signal, current_price=price)
            if order is not None:
                orders.append(_serialize_order(order))

    # Gather results
    summary = engine.portfolio_summary()
    metrics = calculate_metrics(engine.get_events())

    return BacktestResponse(
        total_orders=summary.total_orders,
        open_positions=summary.open_positions,
        equity=round(summary.equity, 2),
        total_pnl=round(summary.total_pnl, 2),
        metrics=asdict(metrics),
        orders=orders,
    )


@app.get("/engine/positions")
def get_positions():
    """Return all open positions."""
    if engine is None:
        raise HTTPException(status_code=404, detail="No engine running. POST /engine/run first.")

    positions = engine.get_all_positions()
    result = {}
    for symbol, pos in positions.items():
        result[symbol] = {
            "symbol": pos.symbol,
            "side": pos.side.value,
            "quantity": pos.quantity,
            "entry_price": pos.entry_price,
            "current_price": pos.current_price,
            "unrealized_pnl": pos.unrealized_pnl,
            "realized_pnl": pos.realized_pnl,
        }
    return {"positions": result}


@app.get("/engine/metrics")
def get_metrics():
    """Return performance metrics from the last run."""
    if engine is None:
        raise HTTPException(status_code=404, detail="No engine running. POST /engine/run first.")

    metrics = engine.performance()
    return {"metrics": asdict(metrics)}


@app.get("/engine/summary")
def get_summary():
    """Return portfolio summary snapshot."""
    if engine is None:
        raise HTTPException(status_code=404, detail="No engine running. POST /engine/run first.")

    summary = engine.portfolio_summary()
    return {
        "equity": summary.equity,
        "open_positions": summary.open_positions,
        "total_orders": summary.total_orders,
        "unrealized_pnl": summary.unrealized_pnl,
        "realized_pnl": summary.realized_pnl,
        "total_pnl": summary.total_pnl,
        "total_events": summary.total_events,
        "is_halted": summary.is_halted,
        "halt_reason": summary.halt_reason,
    }


@app.get("/engine/export")
def export_trades():
    """Export trade history as a CSV file download."""
    if engine is None:
        raise HTTPException(status_code=404, detail="No engine running. POST /engine/run first.")

    os.makedirs("data", exist_ok=True)
    filepath = engine.export_trades("data/trades.csv")
    return FileResponse(
        path=filepath,
        media_type="text/csv",
        filename="trades.csv",
    )


@app.get("/engine/events")
def get_events(limit: int = Query(default=50, ge=1, le=1000)):
    """Return the last N events from the event store."""
    if engine is None:
        raise HTTPException(status_code=404, detail="No engine running. POST /engine/run first.")

    all_events = engine.get_events()
    recent = all_events[-limit:]
    return {"events": [_serialize_event(e) for e in recent], "total": len(all_events)}
