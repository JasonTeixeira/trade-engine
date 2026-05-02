"use client"

import { useState, useEffect, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Activity,
  Play,
  Download,
  ChevronDown,
  ChevronUp,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Target,
  AlertTriangle,
  Zap,
  Loader2,
} from "lucide-react"
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts"
import { toast } from "sonner"
import { api, type BacktestConfig, type BacktestResult } from "@/lib/api"
import { generateSamplePrices } from "@/lib/sample-data"

// ---------------------------------------------------------------------------
// Metric Card
// ---------------------------------------------------------------------------
function MetricCard({
  label,
  value,
  prefix = "",
  suffix = "",
  colored = false,
  icon: Icon,
}: {
  label: string
  value: number | string
  prefix?: string
  suffix?: string
  colored?: boolean
  icon?: React.ComponentType<{ className?: string }>
}) {
  const num = typeof value === "number" ? value : parseFloat(value)
  const isPositive = num >= 0
  const color = colored
    ? isPositive
      ? "text-[#10B981]"
      : "text-[#EF4444]"
    : "text-[#FAFAFA]"

  const formatted =
    typeof value === "number"
      ? Number.isInteger(value)
        ? value.toLocaleString()
        : value.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })
      : value

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-lg border border-[#27272A] bg-[#18181B] p-4"
    >
      <div className="flex items-center gap-2 mb-1">
        {Icon && <Icon className="h-4 w-4 text-[#71717A]" />}
        <span className="text-xs font-medium uppercase tracking-wider text-[#71717A]">
          {label}
        </span>
      </div>
      <p className={`text-xl font-semibold font-mono ${color}`}>
        {prefix}
        {formatted}
        {suffix}
      </p>
    </motion.div>
  )
}

// ---------------------------------------------------------------------------
// State Badge
// ---------------------------------------------------------------------------
function StateBadge({ state }: { state: string }) {
  const colors: Record<string, string> = {
    FILLED: "bg-[#10B981]/15 text-[#10B981] border-[#10B981]/30",
    REJECTED: "bg-[#EF4444]/15 text-[#EF4444] border-[#EF4444]/30",
    PARTIAL_FILL: "bg-[#EAB308]/15 text-[#EAB308] border-[#EAB308]/30",
    PENDING: "bg-[#06B6D4]/15 text-[#06B6D4] border-[#06B6D4]/30",
  }
  const cls = colors[state] || "bg-[#27272A] text-[#A1A1AA] border-[#3F3F46]"
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${cls}`}
    >
      {state}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Side Badge
// ---------------------------------------------------------------------------
function SideBadge({ side }: { side: string }) {
  const isBuy = side.toUpperCase() === "BUY"
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-bold ${
        isBuy
          ? "bg-[#10B981]/15 text-[#10B981]"
          : "bg-[#EF4444]/15 text-[#EF4444]"
      }`}
    >
      {side}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Main Dashboard
// ---------------------------------------------------------------------------
export default function Dashboard() {
  // Connection status
  const [connected, setConnected] = useState(false)
  const [strategies, setStrategies] = useState<string[]>([
    "momentum",
    "mean_reversion",
    "breakout",
  ])

  // Config
  const [strategy, setStrategy] = useState("momentum")
  const [symbol, setSymbol] = useState("ES")
  const [initialCapital, setInitialCapital] = useState(100000)
  const [maxPositionPct, setMaxPositionPct] = useState(5)
  const [maxDrawdownPct, setMaxDrawdownPct] = useState(10)
  const [slippageBps, setSlippageBps] = useState(5)
  const [commission, setCommission] = useState(2.5)

  // Results
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Events
  const [events, setEvents] = useState<
    Array<{ type: string; timestamp: string; data?: Record<string, unknown> }>
  >([])
  const [eventsOpen, setEventsOpen] = useState(false)

  // Strategy dropdown open
  const [strategyOpen, setStrategyOpen] = useState(false)

  // Health check on mount
  useEffect(() => {
    api
      .health()
      .then((h) => {
        setConnected(true)
        if (h.strategies?.length) setStrategies(h.strategies)
      })
      .catch(() => setConnected(false))
  }, [])

  // Run backtest
  const runBacktest = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const prices = generateSamplePrices(5000, 200)
      const config: BacktestConfig = {
        strategy,
        symbol,
        initial_capital: initialCapital,
        prices,
        max_position_pct: maxPositionPct / 100,
        max_drawdown_pct: maxDrawdownPct / 100,
        slippage_bps: slippageBps,
        commission,
      }
      const res = await api.runBacktest(config)
      setResult(res)
      toast.success("Backtest complete", {
        description: `${res.metrics.total_trades} trades, ${(res.metrics.win_rate * 100).toFixed(1)}% win rate`,
      })

      // Fetch events
      try {
        const ev = await api.getEvents(20)
        setEvents(Array.isArray(ev) ? ev : [])
      } catch {
        /* events optional */
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Backtest failed"
      setError(msg)
      toast.error("Backtest failed", { description: msg })
    } finally {
      setIsLoading(false)
    }
  }, [
    strategy,
    symbol,
    initialCapital,
    maxPositionPct,
    maxDrawdownPct,
    slippageBps,
    commission,
  ])

  // Export CSV
  const handleExport = useCallback(async () => {
    try {
      const res = await api.exportCSV()
      if (!res.ok) throw new Error("Export failed")
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `trade-engine-export-${Date.now()}.csv`
      a.click()
      URL.revokeObjectURL(url)
      toast.success("CSV exported")
    } catch {
      toast.error("Export failed")
    }
  }, [])

  // Build equity curve data
  const equityCurve = result
    ? (() => {
        const prices = generateSamplePrices(5000, 200)
        const pnlPerBar = result.total_pnl / prices.length
        return prices.map((p, i) => ({
          bar: i,
          price: p,
          equity: Math.round((initialCapital + pnlPerBar * (i + 1)) * 100) / 100,
        }))
      })()
    : []

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {/* ----------------------------------------------------------------- */}
      {/* Top Bar                                                           */}
      {/* ----------------------------------------------------------------- */}
      <header className="flex items-center justify-between border-b border-[#27272A] bg-[#18181B]/60 backdrop-blur px-6 py-3 shrink-0">
        <div className="flex items-center gap-3">
          <Activity className="h-6 w-6 text-[#06B6D4]" />
          <h1 className="text-lg font-semibold tracking-tight">
            Trade Engine
          </h1>
          <span className="hidden sm:inline text-xs text-[#71717A] border-l border-[#27272A] pl-3 ml-1">
            Order Execution Platform
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span
            className={`h-2 w-2 rounded-full ${connected ? "bg-[#10B981]" : "bg-[#EF4444]"}`}
          />
          <span className="text-[#A1A1AA]">
            {connected ? "Connected" : "Disconnected"}
          </span>
        </div>
      </header>

      {/* ----------------------------------------------------------------- */}
      {/* Main Content                                                      */}
      {/* ----------------------------------------------------------------- */}
      <div className="flex flex-1 overflow-hidden">
        {/* ============================================================= */}
        {/* Left Panel — Config                                            */}
        {/* ============================================================= */}
        <aside className="w-[40%] min-w-[340px] max-w-[520px] border-r border-[#27272A] overflow-y-auto p-6 space-y-6 shrink-0">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-[#A1A1AA]">
            Backtest Configuration
          </h2>

          {/* Strategy selector */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[#A1A1AA]">
              Strategy
            </label>
            <div className="relative">
              <button
                type="button"
                onClick={() => setStrategyOpen(!strategyOpen)}
                className="flex w-full items-center justify-between rounded-md border border-[#27272A] bg-[#18181B] px-3 py-2 text-sm hover:border-[#3F3F46] focus:outline-none focus:ring-1 focus:ring-[#06B6D4]"
              >
                <span className="capitalize">{strategy.replace("_", " ")}</span>
                <ChevronDown className="h-4 w-4 text-[#71717A]" />
              </button>
              <AnimatePresence>
                {strategyOpen && (
                  <motion.ul
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    className="absolute z-10 mt-1 w-full rounded-md border border-[#27272A] bg-[#18181B] py-1 shadow-lg"
                  >
                    {strategies.map((s) => (
                      <li key={s}>
                        <button
                          type="button"
                          onClick={() => {
                            setStrategy(s)
                            setStrategyOpen(false)
                          }}
                          className={`w-full px-3 py-2 text-left text-sm hover:bg-[#27272A] capitalize ${
                            s === strategy ? "text-[#06B6D4]" : ""
                          }`}
                        >
                          {s.replace("_", " ")}
                        </button>
                      </li>
                    ))}
                  </motion.ul>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* Symbol */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[#A1A1AA]">Symbol</label>
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              className="w-full rounded-md border border-[#27272A] bg-[#18181B] px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#06B6D4]"
              placeholder="ES"
            />
          </div>

          {/* Initial Capital */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[#A1A1AA]">
              Initial Capital
            </label>
            <input
              type="number"
              value={initialCapital}
              onChange={(e) => setInitialCapital(Number(e.target.value))}
              className="w-full rounded-md border border-[#27272A] bg-[#18181B] px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-[#06B6D4]"
            />
          </div>

          {/* Risk Parameters */}
          <div className="space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-[#71717A]">
              Risk Parameters
            </h3>

            {/* Max Position % */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs text-[#A1A1AA]">
                  Max Position Size
                </label>
                <span className="text-xs font-mono text-[#06B6D4]">
                  {maxPositionPct}%
                </span>
              </div>
              <input
                type="range"
                min={1}
                max={20}
                value={maxPositionPct}
                onChange={(e) => setMaxPositionPct(Number(e.target.value))}
                className="w-full accent-[#06B6D4] h-1.5 rounded-full appearance-none bg-[#27272A] cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[#06B6D4]"
              />
              <div className="flex justify-between text-[10px] text-[#71717A]">
                <span>1%</span>
                <span>20%</span>
              </div>
            </div>

            {/* Max Drawdown % */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs text-[#A1A1AA]">Max Drawdown</label>
                <span className="text-xs font-mono text-[#06B6D4]">
                  {maxDrawdownPct}%
                </span>
              </div>
              <input
                type="range"
                min={1}
                max={30}
                value={maxDrawdownPct}
                onChange={(e) => setMaxDrawdownPct(Number(e.target.value))}
                className="w-full accent-[#06B6D4] h-1.5 rounded-full appearance-none bg-[#27272A] cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[#06B6D4]"
              />
              <div className="flex justify-between text-[10px] text-[#71717A]">
                <span>1%</span>
                <span>30%</span>
              </div>
            </div>
          </div>

          {/* Execution Parameters */}
          <div className="space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-[#71717A]">
              Execution
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-xs text-[#A1A1AA]">
                  Slippage (bps)
                </label>
                <input
                  type="number"
                  value={slippageBps}
                  onChange={(e) => setSlippageBps(Number(e.target.value))}
                  className="w-full rounded-md border border-[#27272A] bg-[#18181B] px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-[#06B6D4]"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-[#A1A1AA]">Commission ($)</label>
                <input
                  type="number"
                  step={0.01}
                  value={commission}
                  onChange={(e) => setCommission(Number(e.target.value))}
                  className="w-full rounded-md border border-[#27272A] bg-[#18181B] px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-[#06B6D4]"
                />
              </div>
            </div>
          </div>

          {/* Run Button */}
          <button
            type="button"
            onClick={runBacktest}
            disabled={isLoading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#06B6D4] px-4 py-3 text-sm font-semibold text-[#09090B] transition-colors hover:bg-[#22D3EE] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Running Backtest...
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Run Backtest
              </>
            )}
          </button>

          {error && (
            <div className="rounded-md border border-[#EF4444]/30 bg-[#EF4444]/10 px-3 py-2 text-xs text-[#EF4444]">
              {error}
            </div>
          )}
        </aside>

        {/* ============================================================= */}
        {/* Right Panel — Results                                          */}
        {/* ============================================================= */}
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          {!result && !isLoading && (
            <div className="flex flex-col items-center justify-center h-full text-[#71717A] gap-4">
              <BarChart3 className="h-16 w-16 opacity-30" />
              <p className="text-sm">
                Configure parameters and run a backtest to see results
              </p>
            </div>
          )}

          {isLoading && (
            <div className="flex flex-col items-center justify-center h-full gap-4">
              <Loader2 className="h-10 w-10 text-[#06B6D4] animate-spin" />
              <p className="text-sm text-[#A1A1AA]">
                Running backtest simulation...
              </p>
            </div>
          )}

          <AnimatePresence>
            {result && !isLoading && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="space-y-6"
              >
                {/* ---- Metrics Cards ---- */}
                <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
                  <MetricCard
                    label="Equity"
                    value={result.equity}
                    prefix="$"
                    colored
                    icon={TrendingUp}
                  />
                  <MetricCard
                    label="Total P&L"
                    value={result.total_pnl}
                    prefix="$"
                    colored
                    icon={result.total_pnl >= 0 ? TrendingUp : TrendingDown}
                  />
                  <MetricCard
                    label="Win Rate"
                    value={(result.metrics.win_rate * 100).toFixed(1)}
                    suffix="%"
                    colored
                    icon={Target}
                  />
                  <MetricCard
                    label="Sharpe Ratio"
                    value={result.metrics.sharpe_ratio.toFixed(2)}
                    colored
                    icon={Zap}
                  />
                  <MetricCard
                    label="Max Drawdown"
                    value={(result.metrics.max_drawdown * 100).toFixed(1)}
                    suffix="%"
                    colored={false}
                    icon={AlertTriangle}
                  />
                  <MetricCard
                    label="Profit Factor"
                    value={result.metrics.profit_factor.toFixed(2)}
                    colored
                    icon={BarChart3}
                  />
                </div>

                {/* ---- Secondary Metrics ---- */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  <MetricCard
                    label="Total Trades"
                    value={result.metrics.total_trades}
                  />
                  <MetricCard
                    label="Avg Win"
                    value={result.metrics.avg_win}
                    prefix="$"
                    colored
                  />
                  <MetricCard
                    label="Avg Loss"
                    value={result.metrics.avg_loss}
                    prefix="$"
                    colored
                  />
                  <MetricCard
                    label="Open Positions"
                    value={result.open_positions}
                  />
                </div>

                {/* ---- Equity Curve ---- */}
                <div className="rounded-lg border border-[#27272A] bg-[#18181B] p-4">
                  <h3 className="text-sm font-semibold text-[#A1A1AA] mb-4">
                    Equity Curve
                  </h3>
                  <div className="h-[280px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={equityCurve}>
                        <defs>
                          <linearGradient
                            id="equityGrad"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                          >
                            <stop
                              offset="0%"
                              stopColor="#06B6D4"
                              stopOpacity={0.3}
                            />
                            <stop
                              offset="100%"
                              stopColor="#06B6D4"
                              stopOpacity={0}
                            />
                          </linearGradient>
                        </defs>
                        <CartesianGrid
                          strokeDasharray="3 3"
                          stroke="#27272A"
                          vertical={false}
                        />
                        <XAxis
                          dataKey="bar"
                          tick={{ fill: "#71717A", fontSize: 11 }}
                          axisLine={{ stroke: "#27272A" }}
                          tickLine={false}
                        />
                        <YAxis
                          tick={{ fill: "#71717A", fontSize: 11 }}
                          axisLine={{ stroke: "#27272A" }}
                          tickLine={false}
                          tickFormatter={(v: number) =>
                            `$${(v / 1000).toFixed(0)}k`
                          }
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: "#18181B",
                            border: "1px solid #27272A",
                            borderRadius: 8,
                            color: "#FAFAFA",
                            fontSize: 12,
                          }}
                          formatter={(value) => [
                            `$${Number(value).toLocaleString()}`,
                            "Equity",
                          ]}
                        />
                        <Area
                          type="monotone"
                          dataKey="equity"
                          stroke="#06B6D4"
                          strokeWidth={2}
                          fill="url(#equityGrad)"
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* ---- Orders Table ---- */}
                <div className="rounded-lg border border-[#27272A] bg-[#18181B] overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-3 border-b border-[#27272A]">
                    <h3 className="text-sm font-semibold text-[#A1A1AA]">
                      Orders ({result.orders.length})
                    </h3>
                    <button
                      type="button"
                      onClick={handleExport}
                      className="flex items-center gap-1.5 rounded-md border border-[#27272A] bg-[#09090B] px-3 py-1.5 text-xs text-[#A1A1AA] hover:text-[#FAFAFA] hover:border-[#3F3F46] transition-colors"
                    >
                      <Download className="h-3.5 w-3.5" />
                      Export CSV
                    </button>
                  </div>
                  <div className="overflow-x-auto max-h-[320px] overflow-y-auto">
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 bg-[#18181B]">
                        <tr className="border-b border-[#27272A] text-left text-xs font-medium uppercase tracking-wider text-[#71717A]">
                          <th className="px-4 py-2">Order ID</th>
                          <th className="px-4 py-2">Side</th>
                          <th className="px-4 py-2">Qty</th>
                          <th className="px-4 py-2">State</th>
                          <th className="px-4 py-2">Fill Price</th>
                          <th className="px-4 py-2">Rejection</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.orders.map((order, i) => (
                          <tr
                            key={order.order_id || i}
                            className="border-b border-[#27272A]/50 hover:bg-[#27272A]/30 transition-colors"
                          >
                            <td className="px-4 py-2 font-mono text-xs text-[#A1A1AA]">
                              {order.order_id.slice(0, 8)}...
                            </td>
                            <td className="px-4 py-2">
                              <SideBadge side={order.side} />
                            </td>
                            <td className="px-4 py-2 font-mono">
                              {order.quantity}
                            </td>
                            <td className="px-4 py-2">
                              <StateBadge state={order.state} />
                            </td>
                            <td className="px-4 py-2 font-mono">
                              {order.fill_price > 0
                                ? `$${order.fill_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}`
                                : "--"}
                            </td>
                            <td className="px-4 py-2 text-xs text-[#71717A]">
                              {order.rejection_reason || "--"}
                            </td>
                          </tr>
                        ))}
                        {result.orders.length === 0 && (
                          <tr>
                            <td
                              colSpan={6}
                              className="px-4 py-8 text-center text-[#71717A]"
                            >
                              No orders generated
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* ---- Events Panel ---- */}
                {events.length > 0 && (
                  <div className="rounded-lg border border-[#27272A] bg-[#18181B] overflow-hidden">
                    <button
                      type="button"
                      onClick={() => setEventsOpen(!eventsOpen)}
                      className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold text-[#A1A1AA] hover:bg-[#27272A]/30 transition-colors"
                    >
                      <span>Events ({events.length})</span>
                      {eventsOpen ? (
                        <ChevronUp className="h-4 w-4" />
                      ) : (
                        <ChevronDown className="h-4 w-4" />
                      )}
                    </button>
                    <AnimatePresence>
                      {eventsOpen && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          className="overflow-hidden"
                        >
                          <div className="max-h-[240px] overflow-y-auto border-t border-[#27272A]">
                            {events.map((ev, i) => (
                              <div
                                key={i}
                                className="flex items-center gap-3 border-b border-[#27272A]/50 px-4 py-2 text-xs"
                              >
                                <span className="rounded bg-[#06B6D4]/15 px-2 py-0.5 font-mono text-[#06B6D4]">
                                  {ev.type}
                                </span>
                                <span className="text-[#71717A] font-mono">
                                  {ev.timestamp}
                                </span>
                              </div>
                            ))}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </main>
      </div>
    </div>
  )
}
