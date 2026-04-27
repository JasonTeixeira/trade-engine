# trade-engine

Event-driven order execution engine for algorithmic trading. Handles the full order lifecycle — from signal to fill to P&L — with state machines, position tracking, and risk management.

```
Signal → Order → Route → Fill → Position → P&L
         │                  │
         ├── REJECTED       ├── PARTIAL_FILL
         └── CANCELLED      └── SLIPPAGE
```

## Why This Exists

Most open-source trading tools are either backtesting frameworks (simulate trades on historical data) or broker API wrappers (send orders, hope for the best). Neither handles the hard part: **managing order state in a production system where things go wrong.**

This engine handles:
- Orders that partially fill
- Fills at prices different from what you expected (slippage)
- Rejected orders (insufficient margin, market closed, invalid symbol)
- Position sizing based on account risk
- Real-time P&L tracking with unrealized/realized split
- Event sourcing — every state change is recorded and replayable

## Architecture

```
                    ┌─────────────┐
                    │  Strategy   │  Generates signals
                    │  (yours)    │  BUY/SELL/FLAT
                    └──────┬──────┘
                           │ Signal
                    ┌──────▼──────┐
                    │    Risk     │  Position sizing
                    │   Manager   │  Max drawdown check
                    └──────┬──────┘
                           │ Sized Order
                    ┌──────▼──────┐
                    │   Order     │  State machine
                    │   Manager   │  PENDING → SUBMITTED → FILLED
                    └──────┬──────┘
                           │ Order Events
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌───▼────┐ ┌────▼─────┐
        │  Broker   │ │Position│ │  Event   │
        │  Router   │ │Tracker │ │  Store   │
        │ (sim/live)│ │ P&L    │ │ (append) │
        └───────────┘ └────────┘ └──────────┘
```

## Quick Start

```bash
pip install -r requirements.txt
python -m pytest tests/ -v

# Run the example
python examples/momentum_example.py
```

## Core Concepts

### Order State Machine

Every order transitions through a strict state machine. No skipping states. No invalid transitions.

```
                 ┌─── REJECTED
                 │
CREATED ──► PENDING ──► SUBMITTED ──► PARTIAL_FILL ──► FILLED
                 │           │                           │
                 │           └──► CANCELLED              │
                 │                                       │
                 └───────────────────────────────────────►│
                                                     CLOSED
```

Valid transitions are enforced in code. An order in `FILLED` state cannot be cancelled. An order in `REJECTED` state cannot be resubmitted. This prevents the class of bugs where orders end up in impossible states.

### Position Tracking

Positions track entry price, current price, quantity, and P&L:

```python
position = engine.get_position("ES")
# Position(symbol='ES', side='LONG', quantity=2, 
#          entry_price=4521.25, current_price=4525.50,
#          unrealized_pnl=212.50, realized_pnl=0.00)
```

### Risk Management

The risk manager enforces rules before any order is submitted:

- **Max position size**: No single position exceeds N% of account
- **Max drawdown**: Trading halts if drawdown exceeds threshold
- **Max daily loss**: Stops trading for the day after N% loss
- **Correlation check**: Warns if adding correlated exposure

### Event Sourcing

Every state change emits an event. Events are append-only and immutable:

```python
events = engine.get_events(order_id="ORD-001")
# [OrderCreated(price=4521.25, qty=2),
#  OrderSubmitted(broker='sim', timestamp=...),
#  OrderFilled(fill_price=4521.50, slippage=0.25),
#  PositionOpened(symbol='ES', side='LONG', qty=2)]
```

You can replay events to reconstruct any past state — useful for debugging, auditing, and regulatory compliance.

## Usage

### Basic Example

```python
from trade_engine import Engine, SimulatedBroker
from trade_engine.risk import RiskManager
from trade_engine.models import Signal, Side

# Initialize
broker = SimulatedBroker(initial_capital=100_000, slippage_bps=5)
risk = RiskManager(max_position_pct=0.05, max_drawdown_pct=0.10)
engine = Engine(broker=broker, risk_manager=risk)

# Submit a signal
signal = Signal(symbol="ES", side=Side.BUY, strength=0.8)
order = engine.submit_signal(signal)

# Check order state
print(order.state)  # OrderState.FILLED

# Check position
position = engine.get_position("ES")
print(f"P&L: ${position.unrealized_pnl:.2f}")

# Close position
engine.close_position("ES")
```

### Custom Strategy

```python
from trade_engine import Engine
from trade_engine.strategies import Strategy
from trade_engine.models import Signal, Side

class MomentumStrategy(Strategy):
    def __init__(self, lookback: int = 20, threshold: float = 0.02):
        self.lookback = lookback
        self.threshold = threshold

    def on_bar(self, bar, positions) -> Signal | None:
        returns = bar.close.pct_change(self.lookback).iloc[-1]

        if returns > self.threshold and "ES" not in positions:
            return Signal(symbol="ES", side=Side.BUY, strength=returns)
        elif returns < -self.threshold and "ES" in positions:
            return Signal(symbol="ES", side=Side.SELL, strength=abs(returns))

        return None
```

## Module Structure

```
trade_engine/
├── engine.py          # Core engine — orchestrates everything
├── models.py          # Order, Position, Signal, Fill dataclasses
├── order_manager.py   # Order state machine with transition validation
├── position_tracker.py # Position tracking with P&L calculation
├── event_store.py     # Append-only event log
├── brokers/
│   ├── base.py        # Abstract broker interface
│   └── simulated.py   # Simulated broker with slippage model
├── risk/
│   ├── manager.py     # Pre-trade risk checks
│   └── rules.py       # Individual risk rules
└── strategies/
    ├── base.py        # Strategy interface
    └── momentum.py    # Example momentum strategy
```

## Testing

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=trade_engine --cov-report=term-missing

# Specific module
pytest tests/test_order_manager.py -v
```

## Design Decisions

**Why event sourcing?** Trading systems need audit trails. If a regulator asks "why did you buy 100 shares at 3:47pm?", you need to replay the exact sequence of events that led to that decision. Event sourcing makes this trivial.

**Why state machines for orders?** Because `order.status = "filled"` is how bugs happen. State machines enforce that only valid transitions occur. You can't accidentally set a cancelled order to filled.

**Why simulated broker first?** Live broker integrations are complex and broker-specific. The simulated broker lets you develop and test strategies without any external dependencies. Live broker adapters plug in later without changing any strategy code.

## Author

**Jason Teixeira** — [sageideas.dev](https://sageideas.dev) | Active futures trader (ES, NQ, CL, GC)

Built from patterns used in real trading across 8 symbols on NinjaTrader. The architecture reflects lessons from managing real orders where mistakes cost real money.
