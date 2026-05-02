"""Export trade history and events to CSV for Nexural Research analysis."""
import csv
from pathlib import Path
from datetime import datetime, timezone
from models.events import PositionClosed, OrderFilled

def export_trades_csv(events: list, filepath: str = "data/trades.csv") -> str:
    """Export closed positions to NinjaTrader-compatible CSV format."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    closes = [e for e in events if isinstance(e, PositionClosed)]
    fills = [e for e in events if isinstance(e, OrderFilled)]

    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "TradeNumber", "Symbol", "EntryTime", "ExitTime",
            "PnL", "HoldDurationSeconds"
        ])
        for i, close in enumerate(closes, 1):
            writer.writerow([
                i, close.symbol, "", close.timestamp.isoformat(),
                round(close.realized_pnl, 2), round(close.hold_duration_seconds, 1)
            ])

    return filepath

def export_events_csv(events: list, filepath: str = "data/events.csv") -> str:
    """Export all events to CSV for audit trail."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["EventID", "EventType", "Timestamp", "Details"])
        for event in events:
            details = {k: v for k, v in event.__dict__.items()
                      if k not in ('event_id', 'timestamp') and not k.startswith('_')}
            # Convert datetime values to strings
            for k, v in details.items():
                if isinstance(v, datetime):
                    details[k] = v.isoformat()
            writer.writerow([
                event.event_id, type(event).__name__,
                event.timestamp.isoformat(), str(details)
            ])

    return filepath
