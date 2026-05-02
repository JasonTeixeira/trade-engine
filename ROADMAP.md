# Trade Engine — Roadmap to 99/100

Current score: **78/100** (as of 2026-05-02, revised after deep audit)

Repo: https://github.com/JasonTeixeira/trade-engine
Live: https://trade-engine-two.vercel.app

---

## What's Done (78/100)

### Core Engine (Python)
- [x] Event-driven: Signal → Risk → Order → Broker → Fill → Position → P&L
- [x] Strict order state machine (7 states, validated transitions)
- [x] 3 strategies: Momentum (SMA), Mean Reversion (Bollinger), Breakout (Donchian)
- [x] Risk manager: position sizing, max drawdown, daily loss, max positions
- [x] SimulatedBroker: slippage, commissions, partial fills, rejections
- [x] SQLite PersistentEventStore (survives restarts)
- [x] Performance metrics: Sharpe, drawdown, win rate, profit factor
- [x] CSV export (NinjaTrader-compatible)
- [x] Structured logging, timezone-aware timestamps
- [x] FastAPI server (13 endpoints) + Nexural Research integration
- [x] 57 tests, 100% passing

### Frontend Dashboard (Next.js 16)
- [x] Self-contained Vercel deployment (TypeScript engine embedded)
- [x] Strategy selector, risk parameter controls
- [x] Equity curve chart (Recharts)
- [x] 10 metric cards (Sharpe, win rate, drawdown, profit factor, etc.)
- [x] Orders table with colored badges
- [x] Events audit trail panel
- [x] Dark theme, Framer Motion animations

### Critical Bugs Fixed (2026-05-02)
- [x] Double-divide on risk params (position sizing + drawdown)
- [x] Breakout strategy channel includes current bar (never fired)
- [x] Only 200 bars → increased to 1000
- [x] Events API shape mismatch → embedded in result
- [x] Sharpe calculated on per-trade P&L → bar-level equity returns
- [x] Profit factor 999 → ∞ symbol

---

## Remaining Bugs to Fix (Score +5)

### Backend (Python)
| Bug | File | Fix |
|-----|------|-----|
| `RiskManager._peak_equity` starts at 0 → drawdown check disabled on fresh engine | `risk/manager.py:50` | Init from `initial_capital` in constructor |
| `SimulatedBroker.equity` = cash only, no unrealized P&L → drawdown fires late | `engine/brokers.py:134` | Add `unrealized_pnl` property, sum with capital |
| `close_position` bypasses risk manager → could flip position without risk check | `engine/core.py:146` | Add risk validation for close orders |
| P&L double-counting on scaled positions → `position.realized_pnl` is cumulative | `engine/core.py:179` | Use incremental P&L from `position.reduce()` return |
| `max_correlation` field in RiskManager is dead code | `risk/manager.py:44` | Implement or document as TODO |
| Strategy price lists grow unbounded (memory leak on large backtests) | `strategies/*.py` | Use `collections.deque(maxlen=lookback)` |
| EventStore queries are O(N) linear scans | `engine/event_store.py:41` | Add dict indexes by order_id and symbol |
| PersistentEventStore commits per-event (slow for 10K+ bars) | `engine/persistent_store.py` | Batch commits with `commit()` at end of backtest |

### Frontend (TypeScript)
| Bug | File | Fix |
|-----|------|-----|
| Export CSV always empty (no server state) | `app/api/engine/export/route.ts` | Store last result in module-level cache, serve from there |
| Mobile layout broken (40% sidebar on 390px screen) | `app/page.tsx:268` | Add `lg:flex-row flex-col` responsive stacking |
| No `htmlFor`/`id` on label+input pairs (accessibility) | `app/page.tsx:323+` | Add matching ids |
| Strategy dropdown has no click-outside close | `app/page.tsx:283` | Use `@radix-ui/react-select` (already installed) |
| Equity curve X-axis shows bar index, not dates | `app/page.tsx:587` | Generate simulated dates from start date |
| Radix UI packages installed but unused (bundle bloat) | `package.json` | Either use them or remove them |

---

## Phase 1: Dashboard Enhancements (Score +8) — Est: 3-4 days

### 1.1 Multi-Strategy Comparison
- Run 2-3 strategies side-by-side on same data
- Overlay equity curves on same chart
- Metrics comparison table (Sharpe, win rate, drawdown per strategy)
- Highlight winning strategy

### 1.2 Advanced Charts
- **Drawdown curve** — underwater plot showing current DD over time
- **Trade distribution histogram** — bar chart of individual trade P&L
- **Monthly/weekly returns heatmap** — calendar-style grid
- **Rolling Sharpe chart** — 20/50/100 trade rolling window

### 1.3 Benchmark Comparison
- Buy-and-hold the same instrument as baseline
- Overlay on equity curve
- Show alpha (strategy return - benchmark return)
- Information ratio

### 1.4 Strategy Parameter Controls
- Momentum: SMA period slider (5-100), threshold slider
- Mean Reversion: Bollinger period, z-score threshold
- Breakout: Channel period, exit channel period
- Currently all hardcoded to 20-bar windows

### 1.5 Real OHLCV Data
- Integrate Yahoo Finance API (free) via Next.js API route
- User selects symbol + date range
- Fetch real historical data instead of random walk
- This is the single biggest credibility upgrade

---

## Phase 2: Institutional Metrics (Score +6) — Est: 2-3 days

### Backend (engine/metrics.py)
Add these metrics to `PerformanceMetrics`:
```python
sortino_ratio: float       # downside deviation only
calmar_ratio: float        # annualized return / max drawdown
information_ratio: float   # excess return vs benchmark / tracking error
recovery_factor: float     # total profit / max drawdown $
ulcer_index: float         # continuous drawdown severity
omega_ratio: float         # probability-weighted gain/loss ratio
tail_ratio: float          # 95th percentile / 5th percentile
skewness: float            # return distribution asymmetry
kurtosis: float            # tail thickness
consecutive_wins: int      # longest winning streak
consecutive_losses: int    # longest losing streak
avg_trade_duration: float  # in bars
days_to_recovery: int      # from max drawdown
```

### Frontend
- Display all metrics in expandable "Advanced Metrics" panel
- Color-code based on institutional benchmarks (green = good, red = concerning)

---

## Phase 3: Monte Carlo & Walk-Forward (Score +5) — Est: 3-4 days

### 3.1 Monte Carlo Simulation
- Resample closed trade P&Ls with replacement (1000 iterations)
- Generate equity curve distribution
- Display percentile bands (5th, 25th, 50th, 75th, 95th)
- Calculate probability of ruin
- Show max drawdown distribution

### 3.2 Walk-Forward Optimization
- Divide data into in-sample / out-of-sample windows
- Optimize parameters on in-sample
- Test on out-of-sample
- Show robustness across windows
- Detect overfitting (in-sample >> out-of-sample = overfitted)

### 3.3 Stress Testing
- Simulate 2x, 3x, 5x volatility scenarios
- Show P&L under stress
- Simulate consecutive losing streaks

---

## Phase 4: Real Data & Broker Integration (Score +4) — Est: 3-4 days

### 4.1 Yahoo Finance Integration
```typescript
// frontend/app/api/data/[symbol]/route.ts
import yahooFinance from "yahoo-finance2"

export async function GET(req, { params }) {
  const { symbol } = params
  const result = await yahooFinance.historical(symbol, { period1: "2023-01-01" })
  return NextResponse.json(result.map(r => ({
    date: r.date, open: r.open, high: r.high,
    low: r.low, close: r.close, volume: r.volume
  })))
}
```

### 4.2 Multi-Symbol Support
- Dropdown with common symbols: ES, NQ, SPY, QQQ, AAPL, BTC-USD
- Fetch real data for selected symbol
- Run backtest on real OHLCV bars

### 4.3 CSV Upload
- Drag-and-drop CSV upload
- Auto-detect format (NinjaTrader, TradingView, generic)
- Parse and run backtest on uploaded data

### 4.4 Alpaca Paper Trading Adapter (Python backend)
```python
# engine/brokers/alpaca_broker.py
from alpaca.trading.client import TradingClient
class AlpacaBroker(Broker):
    def submit_order(self, order, current_price):
        # Real order submission to Alpaca
```

---

## Phase 5: Advanced Engine Features (Score +4) — Est: 3-4 days

### 5.1 Advanced Order Types
- Stop-loss orders (automatic exit at price level)
- Take-profit orders (automatic exit at target)
- Trailing stop (stop moves with market)
- Bracket orders (entry + SL + TP as single order)
- OCO (one-cancels-other)

### 5.2 Advanced Risk Controls
- VaR (Value at Risk) calculation
- Volatility-adjusted position sizing
- Sector/correlation exposure limits
- Circuit breakers (max slippage, max rejection rate)

### 5.3 Strategy Enhancements
- Short selling (explicit, not accidental overfill)
- Position scaling (add to winners with risk check)
- Time-based exits (flatten at end of session)
- Multi-timeframe analysis

---

## Phase 6: Production Polish (Score +2) — Est: 1-2 days

### 6.1 Testing
- Short P&L test (currently untested)
- Partial fill P&L test
- Daily reset test
- API endpoint tests with TestClient
- Stress test with 50K bars
- Concurrent backtest request test
- Target: 80+ tests

### 6.2 Documentation
- Fix stale module paths in README
- Add docstring to `_reduce_position`
- Interactive Jupyter notebook tutorial
- Strategy cookbook (10+ example strategies)
- API documentation (OpenAPI/Swagger already auto-generated)

### 6.3 CI/CD
- GitHub Actions: run tests on push, lint with ruff
- Vercel auto-deploy on push to main
- Type checking in CI

### 6.4 Package Publishing
- Add proper `pyproject.toml` with metadata
- Publish to PyPI as `trade-engine`
- Add `py.typed` marker for type stub support

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Frontend (Next.js 16 on Vercel)            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Config Panel  │  │ Equity Curve │  │ Orders Table │  │
│  │ Strategy      │  │ (Recharts)   │  │ Events Trail │  │
│  │ Risk Params   │  │ Drawdown     │  │ CSV Export   │  │
│  │ Run Backtest  │  │ Monte Carlo  │  │ Metrics      │  │
│  └──────┬───────┘  └──────────────┘  └──────────────┘  │
│         │ POST /api/engine/run                          │
│  ┌──────▼──────────────────────────────────────────┐    │
│  │       TypeScript Engine (lib/engine.ts)          │    │
│  │  Strategies → Risk → Orders → Broker → Positions│    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              Python Backend (FastAPI on Railway)         │
│  Same engine in Python + SQLite persistence             │
│  + Nexural Research integration (71+ metrics)           │
│  + Real broker adapters (Alpaca, etc.)                  │
└─────────────────────────────────────────────────────────┘
```

## Scoring Breakdown

| Category | Current | After Phase 1-2 | After Phase 3-4 | After Phase 5-6 |
|----------|---------|----------------|----------------|----------------|
| Engine Correctness | 75 | 85 | 90 | 95 |
| Frontend Dashboard | 70 | 90 | 95 | 98 |
| Strategies | 65 | 75 | 85 | 92 |
| Risk Manager | 70 | 80 | 90 | 95 |
| Metrics | 70 | 90 | 95 | 98 |
| Tests | 75 | 80 | 85 | 95 |
| Data Integration | 40 | 80 | 90 | 95 |
| Documentation | 75 | 80 | 85 | 95 |
| **Overall** | **78** | **86** | **92** | **99** |

## Key Files

| File | Purpose | LOC |
|------|---------|-----|
| `frontend/lib/engine.ts` | TypeScript backtest engine | 370 |
| `frontend/app/page.tsx` | Dashboard UI | 750 |
| `frontend/lib/api.ts` | API client | 103 |
| `engine/core.py` | Python engine orchestrator | 236 |
| `models/orders.py` | Order state machine | 167 |
| `risk/manager.py` | Pre-trade risk checks | 162 |
| `engine/metrics.py` | Performance metrics | 86 |
| `engine/persistent_store.py` | SQLite event persistence | 100 |
| `api/server.py` | FastAPI (13 endpoints) | 346 |
| `tests/` | 57 tests | 641 |
