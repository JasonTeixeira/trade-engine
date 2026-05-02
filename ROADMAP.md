# Trade Engine — Roadmap to 99/100

Current score: **88/100** (as of 2026-05-02)

Repo: https://github.com/JasonTeixeira/trade-engine

---

## What's Done (88/100)

### Core Engine
- [x] Event-driven architecture: Signal → Risk → Order → Broker → Fill → Position → P&L
- [x] Strict order state machine (CREATED→PENDING→SUBMITTED→PARTIAL_FILL→FILLED)
- [x] 3 strategies: Momentum, Mean Reversion, Breakout (Donchian)
- [x] Risk manager: position sizing, max drawdown, daily loss limit, max positions
- [x] SimulatedBroker: slippage, commissions, partial fills, rejections
- [x] Event sourcing: immutable, append-only, full audit trail

### Production Features (NEW)
- [x] SQLite-backed PersistentEventStore (survives restarts, event replay)
- [x] Performance metrics: Sharpe, max drawdown, win rate, profit factor, avg win/loss
- [x] CSV export: NinjaTrader-compatible trades + audit trail events
- [x] Structured logging (trade_engine namespace)
- [x] Timezone-aware timestamps throughout (fixed datetime.utcnow deprecation)
- [x] FastAPI server with 7 endpoints
- [x] Docker image for container deployment

### Tests
- [x] 57 tests, 100% passing
- [x] Covers: state machine, risk, strategies, persistence, metrics, export, timezone

### Documentation
- [x] Comprehensive README with ASCII diagrams
- [x] Architecture documentation

---

## What's Needed for 99/100

### Phase 1: Frontend Dashboard (Score +5) — Est: 2-3 days

Build a Next.js dashboard that connects to the Trade Engine API:

**Pages:**
- `/` — Landing page with engine description
- `/dashboard` — Main dashboard: run backtests, view results
- `/dashboard/backtest` — Strategy configuration + run
- `/dashboard/positions` — Open positions table
- `/dashboard/metrics` — Performance metrics cards + charts
- `/dashboard/events` — Event audit trail table

**Components:**
- Strategy selector (dropdown: momentum, mean_reversion, breakout)
- Price data input (paste CSV or use sample data)
- Risk parameter sliders (max position %, max drawdown %, slippage)
- Equity curve chart (Recharts)
- Order history table with state badges
- Performance metrics cards (Sharpe, win rate, drawdown, profit factor)
- Event timeline

**Tech:**
- Next.js 16, React 19, TypeScript, Tailwind 4, Recharts, Radix UI
- Connect to Trade Engine API at `http://localhost:8001`

**API client (lib/api.ts):**
```typescript
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"

export const tradeEngine = {
  health: () => fetch(`${API}/health`).then(r => r.json()),
  runBacktest: (config) => fetch(`${API}/engine/run`, {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify(config)
  }).then(r => r.json()),
  getPositions: () => fetch(`${API}/engine/positions`).then(r => r.json()),
  getMetrics: () => fetch(`${API}/engine/metrics`).then(r => r.json()),
  getSummary: () => fetch(`${API}/engine/summary`).then(r => r.json()),
  getEvents: (limit=50) => fetch(`${API}/engine/events?limit=${limit}`).then(r => r.json()),
  exportCSV: () => fetch(`${API}/engine/export`),
}
```

### Phase 2: Nexural Research Integration (Score +3) — Est: 1-2 days

**Wire Trade Engine CSV export → Nexural Research analysis:**

1. Add endpoint `POST /research/analyze` to Trade Engine API:
   - Exports current trades to CSV
   - Uploads to Nexural Research API at `/api/upload`
   - Fetches metrics from `/api/analysis/comprehensive`
   - Returns combined result

2. Add "Analyze with Nexural Research" button in dashboard:
   - Calls `/research/analyze`
   - Shows 71+ institutional metrics
   - Shows strategy grade (A+ to F)
   - Shows robustness warnings

**Nexural Research endpoints to use:**
- `POST /api/upload` — upload trade CSV
- `GET /api/analysis/metrics?session_id=X` — 61+ metrics
- `GET /api/robustness/deflated-sharpe?session_id=X` — overfitting detection
- `GET /api/analysis/improvement-report?session_id=X` — recommendations

### Phase 3: Real Broker Adapter (Score +2) — Est: 2-3 days

**Alpaca Paper Trading adapter:**
```python
# engine/brokers/alpaca_broker.py
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest

class AlpacaBroker(Broker):
    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        self._client = TradingClient(api_key, secret_key, paper=paper)
    
    def submit_order(self, order, current_price):
        req = MarketOrderRequest(
            symbol=order.symbol,
            qty=order.quantity,
            side=order.side.value.lower(),
            time_in_force="day",
        )
        alpaca_order = self._client.submit_order(req)
        # Convert to Fill...
```

### Phase 4: Advanced Features (Score +2) — Est: 2-3 days

1. **Advanced order types:**
   - Trailing stop: stop price moves with market
   - Bracket order: entry + stop loss + take profit as one
   - OCO: one-cancels-other

2. **Commission models:**
   - Per-share (equities): $0.005/share
   - Per-contract (futures): $2.50/contract
   - Percentage-based: 0.1% of notional

3. **Circuit breakers:**
   - Max slippage tolerance (reject if slippage > threshold)
   - Max rejection rate alert
   - Volatility halt (if ATR > 3x normal)

4. **Multi-symbol correlation check:**
   - Implement the max_correlation field in RiskManager
   - Use rolling correlation matrix
   - Reject correlated positions (e.g., ES + NQ both long)

### Phase 5: Production Polish (Score +2) — Est: 1 day

1. **Add pyproject.toml** with proper package metadata
2. **GitHub Actions CI** — run tests on push, lint with ruff
3. **Type stubs** — add py.typed marker
4. **Publish to PyPI** as `trade-engine` package
5. **Deploy API to Railway** with Dockerfile

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                │
│  Dashboard → Backtest Config → Results → Metrics    │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP/REST
┌──────────────────────▼──────────────────────────────┐
│                Trade Engine API (FastAPI)            │
│  /engine/run  /engine/metrics  /engine/export       │
│  /research/analyze (→ Nexural Research)             │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                  Trade Engine Core                   │
│  ┌─────────┐  ┌───────────┐  ┌────────────────┐    │
│  │Strategy │→│Risk Manager│→│Order Manager    │    │
│  │(Signal) │  │(Check)    │  │(State Machine) │    │
│  └─────────┘  └───────────┘  └───────┬────────┘    │
│                                       │             │
│  ┌─────────────┐  ┌──────────────────▼──────────┐  │
│  │Position     │←│Broker (Simulated/Alpaca)    │  │
│  │Tracker      │  │(Fill)                       │  │
│  └─────────────┘  └─────────────────────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │ Event Store (SQLite) — Audit Trail           │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                       │ CSV Export
┌──────────────────────▼──────────────────────────────┐
│             Nexural Research (FastAPI)               │
│  71+ Metrics │ Monte Carlo │ Walk-Forward │ Grades  │
└─────────────────────────────────────────────────────┘
```

## Integration with AlphaStream

```
AlphaStream (ML Signals)
  → generates: LONG/SHORT signals with confidence
  → output: signal JSON via API

Trade Engine (Order Execution)
  → consumes: AlphaStream signals
  → executes: with risk management, state machine, slippage modeling
  → output: trade CSV, event log, performance metrics

Nexural Research (Strategy Analysis)
  → consumes: Trade Engine CSV export
  → analyzes: 71+ institutional metrics, Monte Carlo, walk-forward
  → output: strategy grade, robustness warnings, recommendations
```

## Key Files

| File | Purpose |
|------|---------|
| `engine/core.py` | Engine orchestrator |
| `engine/persistent_store.py` | SQLite event persistence |
| `engine/metrics.py` | Sharpe, drawdown, win rate |
| `engine/export.py` | CSV export for Nexural Research |
| `engine/logging.py` | Structured logging |
| `models/orders.py` | Order state machine |
| `models/events.py` | Event sourcing models |
| `risk/manager.py` | Pre-trade risk checks |
| `strategies/` | Momentum, Mean Reversion, Breakout |
| `api/server.py` | FastAPI endpoints |
| `tests/` | 57 tests |

## Test Coverage

| Module | Tests | Status |
|--------|-------|--------|
| Order state machine | 23 | Passing |
| Engine integration | 14 | Passing |
| Strategies | 10 | Passing |
| Persistence | 3 | Passing |
| Metrics | 3 | Passing |
| Export | 2 | Passing |
| Timezone | 2 | Passing |
| **Total** | **57** | **100% pass** |
