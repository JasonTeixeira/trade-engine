export interface BacktestConfig {
  strategy: string
  symbol: string
  initial_capital: number
  prices: number[]
  max_position_pct: number
  max_drawdown_pct: number
  slippage_bps: number
  commission: number
}

export interface BacktestResult {
  total_orders: number
  open_positions: number
  equity: number
  total_pnl: number
  unrealized_pnl: number
  realized_pnl: number
  metrics: {
    total_trades: number
    win_rate: number
    sharpe_ratio: number
    max_drawdown: number
    profit_factor: number
    avg_win: number
    avg_loss: number
    largest_win: number
    largest_loss: number
  }
  orders: Array<{
    order_id: string
    side: string
    quantity: number
    state: string
    fill_price: number
    rejection_reason: string | null
  }>
  events_count: number
  events: Array<{ id: string; type: string; timestamp: string; data: Record<string, unknown> }>
  equity_curve: Array<{ bar: number; equity: number; price: number }>
}

export interface Position {
  symbol: string
  side: string
  quantity: number
  entry_price: number
  unrealized_pnl: number
  realized_pnl: number
}

export interface HealthStatus {
  status: string
  engine_active: boolean
  strategies: string[]
  timestamp: string
}

export const api = {
  health: (): Promise<HealthStatus> =>
    fetch("/api/health").then((r) => r.json()),

  runBacktest: (config: BacktestConfig): Promise<BacktestResult> =>
    fetch("/api/engine/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    }).then((r) => {
      if (!r.ok) throw new Error(`API error: ${r.status}`)
      return r.json()
    }),

  getPositions: (): Promise<Position[]> =>
    fetch("/api/engine/positions").then((r) => r.json()),

  getMetrics: () => fetch("/api/engine/metrics").then((r) => r.json()),

  getSummary: () => fetch("/api/engine/summary").then((r) => r.json()),

  getEvents: (limit = 50) =>
    fetch(`/api/engine/events?limit=${limit}`).then((r) => r.json()),

  exportCSV: () => fetch("/api/engine/export"),

  // Nexural Research integration
  analyzeWithResearch: (): Promise<{
    status: string
    session_id?: string
    analysis?: Record<string, unknown>
    engine_metrics?: Record<string, unknown>
    message?: string
  }> =>
    fetch("/api/research/analyze", { method: "POST" }).then((r) => {
      if (!r.ok) throw new Error(`Research analysis failed: ${r.status}`)
      return r.json()
    }),

  researchStatus: (): Promise<{
    available: boolean
    url: string
    message?: string
  }> => fetch("/api/research/status").then((r) => r.json()),
}
