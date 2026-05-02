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
  GitCompareArrows,
} from "lucide-react"
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
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
  const [strategies] = useState<string[]>([
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

  // Data source
  const [useRealData, setUseRealData] = useState(false)
  const [dataLoading, setDataLoading] = useState(false)
  const [period, setPeriod] = useState("1y")

  // Strategy params
  const [lookback, setLookback] = useState(20)
  const [entryThreshold, setEntryThreshold] = useState(0.002)
  const [numStd, setNumStd] = useState(2.0)
  const [entryLookback, setEntryLookback] = useState(20)
  const [exitLookback, setExitLookback] = useState(10)

  // Results
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Comparison
  const [comparing, setComparing] = useState(false)
  const [comparison, setComparison] = useState<BacktestResult[] | null>(null)

  // Events
  const [events, setEvents] = useState<
    Array<{ type: string; timestamp: string; data?: Record<string, unknown> }>
  >([])
  const [eventsOpen, setEventsOpen] = useState(false)
  const [advancedMetricsOpen, setAdvancedMetricsOpen] = useState(false)

  // Strategy descriptions
  const strategyDescriptions: Record<string, string> = {
    momentum: "Buys when price crosses above the 20-period SMA by a threshold. Exits when price drops below SMA. Trend-following approach.",
    mean_reversion: "Buys when price drops below the lower Bollinger Band (oversold). Exits when price returns to the mean or exceeds the upper band.",
    breakout: "Buys when price breaks above the 20-period Donchian channel high. Exits when price breaks below the channel low. Turtle trader style.",
  }

  // Health check on mount
  useEffect(() => {
    api
      .health()
      .then((h) => {
        setConnected(true)
        void h
      })
      .catch(() => setConnected(false))
  }, [])

  // Run backtest
  const runBacktest = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      let prices: number[]
      if (useRealData) {
        setDataLoading(true)
        const res = await fetch(`/api/data/${symbol}?period=${period}`)
        const data = await res.json()
        if (data.error) throw new Error(data.error)
        prices = data.data.map((bar: { close: number }) => bar.close)
        setDataLoading(false)
      } else {
        prices = generateSamplePrices(5000, 1000)
      }

      const config: BacktestConfig = {
        strategy,
        symbol,
        initial_capital: initialCapital,
        prices,
        max_position_pct: maxPositionPct / 100,
        max_drawdown_pct: maxDrawdownPct / 100,
        slippage_bps: slippageBps,
        commission,
        bar_frequency: useRealData ? "1d" : "1h",
        strategy_params: {
          lookback,
          entry_threshold: entryThreshold,
          num_std: numStd,
          entry_lookback: entryLookback,
          exit_lookback: exitLookback,
        },
      }
      const res = await api.runBacktest(config)
      setResult(res)
      setComparison(null)
      toast.success("Backtest complete", {
        description: `${res.metrics.total_trades} trades, ${(res.metrics.win_rate * 100).toFixed(1)}% win rate`,
      })

      // Use events from backtest result
      if (res.events && Array.isArray(res.events)) {
        setEvents(res.events.slice(-20))
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Backtest failed"
      setError(msg)
      toast.error("Backtest failed", { description: msg })
      setDataLoading(false)
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
    useRealData,
    period,
    lookback,
    entryThreshold,
    numStd,
    entryLookback,
    exitLookback,
  ])

  // Compare all strategies
  const runComparison = useCallback(async () => {
    setComparing(true)
    setError(null)
    try {
      let prices: number[]
      if (useRealData) {
        const res = await fetch(`/api/data/${symbol}?period=${period}`)
        const data = await res.json()
        if (data.error) throw new Error(data.error)
        prices = data.data.map((bar: { close: number }) => bar.close)
      } else {
        prices = generateSamplePrices(5000, 1000)
      }

      const results: BacktestResult[] = []
      for (const strat of strategies) {
        const config: BacktestConfig = {
          strategy: strat,
          symbol,
          initial_capital: initialCapital,
          prices,
          max_position_pct: maxPositionPct / 100,
          max_drawdown_pct: maxDrawdownPct / 100,
          slippage_bps: slippageBps,
          commission,
          bar_frequency: useRealData ? "1d" : "1h",
        }
        const res = await fetch("/api/engine/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(config),
        })
        results.push(await res.json())
      }
      setComparison(results)
      toast.success("Comparison complete", {
        description: `${strategies.length} strategies compared`,
      })
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Comparison failed"
      setError(msg)
      toast.error("Comparison failed", { description: msg })
    } finally {
      setComparing(false)
    }
  }, [
    strategies,
    symbol,
    initialCapital,
    maxPositionPct,
    maxDrawdownPct,
    slippageBps,
    commission,
    useRealData,
    period,
  ])

  // Export CSV
  const handleExport = useCallback(() => {
    if (!result) return
    let csv = "order_id,side,quantity,state,fill_price,rejection_reason\n"
    for (const o of result.orders) {
      csv += `${o.order_id},${o.side},${o.quantity},${o.state},${o.fill_price},${o.rejection_reason || ""}\n`
    }
    const blob = new Blob([csv], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `backtest_${strategy}_${symbol}.csv`
    a.click()
    URL.revokeObjectURL(url)
    toast.success("CSV exported")
  }, [result, strategy, symbol])

  // Use equity curve from backtest result directly
  const equityCurve = result?.equity_curve ?? []

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
      <div className="flex flex-col lg:flex-row flex-1 overflow-hidden">
        {/* ============================================================= */}
        {/* Left Panel — Config                                            */}
        {/* ============================================================= */}
        <aside className="w-full lg:w-[40%] lg:min-w-[340px] lg:max-w-[520px] border-b lg:border-b-0 lg:border-r border-[#27272A] overflow-y-auto p-6 space-y-6 shrink-0">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-[#A1A1AA]">
            Backtest Configuration
          </h2>

          {/* Data Source Toggle */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[#A1A1AA]">Data Source</label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setUseRealData(false)}
                className={`px-3 py-1.5 text-xs rounded-md transition-colors ${!useRealData ? "bg-[#06B6D4] text-black font-semibold" : "bg-[#18181B] text-[#A1A1AA] border border-[#27272A] hover:border-[#3F3F46]"}`}
              >
                Sample Data
              </button>
              <button
                type="button"
                onClick={() => setUseRealData(true)}
                className={`px-3 py-1.5 text-xs rounded-md transition-colors ${useRealData ? "bg-[#06B6D4] text-black font-semibold" : "bg-[#18181B] text-[#A1A1AA] border border-[#27272A] hover:border-[#3F3F46]"}`}
              >
                Real Data (Yahoo Finance)
              </button>
            </div>
            {useRealData && (
              <div className="flex gap-1.5 mt-2">
                {["3mo", "6mo", "1y", "2y"].map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPeriod(p)}
                    className={`px-2.5 py-1 text-xs rounded transition-colors ${period === p ? "bg-[#06B6D4]/20 text-[#06B6D4] border border-[#06B6D4]/30" : "bg-[#18181B] text-[#71717A] border border-[#27272A] hover:border-[#3F3F46]"}`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            )}
            {dataLoading && (
              <div className="flex items-center gap-2 mt-1 text-xs text-[#06B6D4]">
                <Loader2 className="h-3 w-3 animate-spin" />
                Fetching market data...
              </div>
            )}
          </div>

          {/* Strategy selector */}
          <div className="space-y-1.5">
            <label htmlFor="strategy" className="text-xs font-medium text-[#A1A1AA]">
              Strategy
            </label>
            <select
              id="strategy"
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="w-full bg-[#18181B] border border-[#27272A] rounded-lg px-4 py-3 text-[#FAFAFA] focus:border-[#06B6D4] focus:outline-none appearance-none cursor-pointer"
            >
              <option value="momentum">Momentum (SMA Crossover)</option>
              <option value="mean_reversion">Mean Reversion (Bollinger Bands)</option>
              <option value="breakout">Breakout (Donchian Channels)</option>
            </select>
            <p className="text-xs text-[#71717A] mt-2">{strategyDescriptions[strategy]}</p>
          </div>

          {/* Strategy Parameters */}
          {strategy === "momentum" && (
            <div className="space-y-3 p-3 bg-[#0A0A0B] rounded-lg border border-[#27272A]">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-[#71717A]">Strategy Parameters</h4>
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <label className="text-[#71717A]">SMA Period</label>
                  <span className="text-[#06B6D4] font-mono">{lookback}</span>
                </div>
                <input type="range" min={5} max={50} value={lookback} onChange={e => setLookback(Number(e.target.value))} className="w-full accent-[#06B6D4] h-1.5 rounded-full appearance-none bg-[#27272A] cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[#06B6D4]" />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <label className="text-[#71717A]">Entry Threshold</label>
                  <span className="text-[#06B6D4] font-mono">{(entryThreshold * 100).toFixed(1)}%</span>
                </div>
                <input type="range" min={1} max={30} value={entryThreshold * 1000} onChange={e => setEntryThreshold(Number(e.target.value) / 1000)} className="w-full accent-[#06B6D4] h-1.5 rounded-full appearance-none bg-[#27272A] cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[#06B6D4]" />
              </div>
            </div>
          )}

          {strategy === "mean_reversion" && (
            <div className="space-y-3 p-3 bg-[#0A0A0B] rounded-lg border border-[#27272A]">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-[#71717A]">Strategy Parameters</h4>
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <label className="text-[#71717A]">Lookback Period</label>
                  <span className="text-[#06B6D4] font-mono">{lookback}</span>
                </div>
                <input type="range" min={5} max={50} value={lookback} onChange={e => setLookback(Number(e.target.value))} className="w-full accent-[#06B6D4] h-1.5 rounded-full appearance-none bg-[#27272A] cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[#06B6D4]" />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <label className="text-[#71717A]">Std Deviations</label>
                  <span className="text-[#06B6D4] font-mono">{numStd.toFixed(1)}</span>
                </div>
                <input type="range" min={10} max={40} value={numStd * 10} onChange={e => setNumStd(Number(e.target.value) / 10)} className="w-full accent-[#06B6D4] h-1.5 rounded-full appearance-none bg-[#27272A] cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[#06B6D4]" />
              </div>
            </div>
          )}

          {strategy === "breakout" && (
            <div className="space-y-3 p-3 bg-[#0A0A0B] rounded-lg border border-[#27272A]">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-[#71717A]">Strategy Parameters</h4>
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <label className="text-[#71717A]">Entry Lookback</label>
                  <span className="text-[#06B6D4] font-mono">{entryLookback}</span>
                </div>
                <input type="range" min={5} max={55} value={entryLookback} onChange={e => setEntryLookback(Number(e.target.value))} className="w-full accent-[#06B6D4] h-1.5 rounded-full appearance-none bg-[#27272A] cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[#06B6D4]" />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <label className="text-[#71717A]">Exit Lookback</label>
                  <span className="text-[#06B6D4] font-mono">{exitLookback}</span>
                </div>
                <input type="range" min={3} max={30} value={exitLookback} onChange={e => setExitLookback(Number(e.target.value))} className="w-full accent-[#06B6D4] h-1.5 rounded-full appearance-none bg-[#27272A] cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[#06B6D4]" />
              </div>
            </div>
          )}

          {/* Symbol */}
          <div className="space-y-1.5">
            <label htmlFor="symbol" className="text-xs font-medium text-[#A1A1AA]">Symbol</label>
            <input
              id="symbol"
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              className="w-full rounded-md border border-[#27272A] bg-[#18181B] px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#06B6D4]"
              placeholder="ES"
            />
          </div>

          {/* Initial Capital */}
          <div className="space-y-1.5">
            <label htmlFor="initialCapital" className="text-xs font-medium text-[#A1A1AA]">
              Initial Capital
            </label>
            <input
              id="initialCapital"
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
                <label htmlFor="maxPositionPct" className="text-xs text-[#A1A1AA]">
                  Max Position Size
                </label>
                <span className="text-xs font-mono text-[#06B6D4]">
                  {maxPositionPct}%
                </span>
              </div>
              <input
                id="maxPositionPct"
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
                <label htmlFor="maxDrawdownPct" className="text-xs text-[#A1A1AA]">Max Drawdown</label>
                <span className="text-xs font-mono text-[#06B6D4]">
                  {maxDrawdownPct}%
                </span>
              </div>
              <input
                id="maxDrawdownPct"
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
                <label htmlFor="slippageBps" className="text-xs text-[#A1A1AA]">
                  Slippage (bps)
                </label>
                <input
                  id="slippageBps"
                  type="number"
                  value={slippageBps}
                  onChange={(e) => setSlippageBps(Number(e.target.value))}
                  className="w-full rounded-md border border-[#27272A] bg-[#18181B] px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-[#06B6D4]"
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="commission" className="text-xs text-[#A1A1AA]">Commission ($)</label>
                <input
                  id="commission"
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
            disabled={isLoading || comparing}
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

          {/* Compare All Strategies */}
          <button
            type="button"
            onClick={runComparison}
            disabled={isLoading || comparing}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-[#27272A] bg-[#18181B] px-4 py-3 text-sm font-medium text-[#A1A1AA] transition-colors hover:text-[#FAFAFA] hover:border-[#3F3F46] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {comparing ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Comparing Strategies...
              </>
            ) : (
              <>
                <GitCompareArrows className="h-4 w-4" />
                Compare All Strategies
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
          {!result && !isLoading && !comparison && (
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
                    icon={result.total_pnl >= 0 ? TrendingUp : TrendingDown}
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
                    value={result.metrics.profit_factor < 0 ? "\u221E" : result.metrics.profit_factor.toFixed(2)}
                    colored
                    icon={BarChart3}
                  />
                </div>

                {/* ---- Benchmark Cards ---- */}
                {result.benchmark && (
                  <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
                    <MetricCard
                      label="Buy & Hold Return"
                      value={(result.benchmark.buy_hold_return * 100).toFixed(2)}
                      suffix="%"
                      colored
                    />
                    <MetricCard
                      label="Buy & Hold Equity"
                      value={result.benchmark.buy_hold_equity}
                      prefix="$"
                    />
                    <MetricCard
                      label="Alpha"
                      value={(result.benchmark.alpha * 100).toFixed(2)}
                      suffix="%"
                      colored
                    />
                  </div>
                )}

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

                {/* ---- Institutional Metrics ---- */}
                <div className="mt-3">
                  <button
                    onClick={() => setAdvancedMetricsOpen(prev => !prev)}
                    className="text-xs text-[#71717A] hover:text-[#A1A1AA] mb-2 flex items-center gap-1"
                  >
                    <Zap className="h-3 w-3" />
                    Advanced Metrics
                    {advancedMetricsOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                  </button>
                  {advancedMetricsOpen && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      className="grid grid-cols-2 sm:grid-cols-4 gap-2"
                    >
                      <MetricCard label="Sortino" value={result.metrics.sortino_ratio} colored />
                      <MetricCard label="Calmar" value={result.metrics.calmar_ratio} colored />
                      <MetricCard label="Recovery Factor" value={result.metrics.recovery_factor} colored />
                      <MetricCard label="Skewness" value={result.metrics.skewness} />
                      <MetricCard label="Kurtosis" value={result.metrics.kurtosis} />
                      <MetricCard label="Win Streak" value={result.metrics.consecutive_wins} suffix=" trades" />
                      <MetricCard label="Loss Streak" value={result.metrics.consecutive_losses} suffix=" trades" />
                      <MetricCard label="Avg Duration" value={result.metrics.avg_trade_duration} suffix=" bars" />
                    </motion.div>
                  )}
                </div>

                {/* ---- Equity Curve with Benchmark ---- */}
                {(() => {
                  const startDate = new Date(2024, 0, 1)
                  const chartData = result.equity_curve.map((pt, i) => ({
                    ...pt,
                    date: new Date(startDate.getTime() + i * 3600000).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
                  }))

                  // Compute drawdown data
                  let peak = result.equity_curve[0]?.equity ?? 0
                  const drawdownData = result.equity_curve.map((pt, i) => {
                    if (pt.equity > peak) peak = pt.equity
                    const dd = peak > 0 ? ((peak - pt.equity) / peak) * -100 : 0
                    return { date: chartData[i].date, drawdown: dd }
                  })

                  return (
                    <>
                      <div className="rounded-lg border border-[#27272A] bg-[#18181B] p-4">
                        <h3 className="text-sm font-semibold text-[#A1A1AA] mb-4">
                          Equity Curve vs Buy &amp; Hold
                        </h3>
                        <div className="h-[280px]">
                          <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={chartData}>
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
                                dataKey="date"
                                tick={{ fill: "#71717A", fontSize: 11 }}
                                axisLine={{ stroke: "#27272A" }}
                                tickLine={false}
                                interval={Math.floor(result.equity_curve.length / 10)}
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
                                formatter={(value, name) => [
                                  `$${Number(value).toLocaleString()}`,
                                  name === "equity" ? "Strategy" : "Buy & Hold",
                                ]}
                              />
                              <Legend
                                verticalAlign="top"
                                height={28}
                                formatter={(value: string) => value === "equity" ? "Strategy" : "Buy & Hold"}
                                wrapperStyle={{ fontSize: 11, color: "#A1A1AA" }}
                              />
                              <Area
                                type="monotone"
                                dataKey="equity"
                                stroke="#06B6D4"
                                strokeWidth={2}
                                fill="url(#equityGrad)"
                                name="equity"
                              />
                              <Area
                                type="monotone"
                                dataKey="benchmark"
                                stroke="#71717A"
                                fill="none"
                                strokeDasharray="5 5"
                                strokeWidth={1.5}
                                name="benchmark"
                              />
                            </AreaChart>
                          </ResponsiveContainer>
                        </div>
                      </div>

                      {/* ---- Drawdown Curve ---- */}
                      <div className="rounded-lg border border-[#27272A] bg-[#18181B] p-4">
                        <h3 className="text-sm font-semibold text-[#A1A1AA] mb-4">
                          Drawdown (%)
                        </h3>
                        <div className="h-[200px]">
                          <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={drawdownData}>
                              <defs>
                                <linearGradient
                                  id="drawdownGrad"
                                  x1="0"
                                  y1="0"
                                  x2="0"
                                  y2="1"
                                >
                                  <stop
                                    offset="0%"
                                    stopColor="#EF4444"
                                    stopOpacity={0.3}
                                  />
                                  <stop
                                    offset="100%"
                                    stopColor="#EF4444"
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
                                dataKey="date"
                                tick={{ fill: "#71717A", fontSize: 11 }}
                                axisLine={{ stroke: "#27272A" }}
                                tickLine={false}
                                interval={Math.floor(drawdownData.length / 10)}
                              />
                              <YAxis
                                tick={{ fill: "#71717A", fontSize: 11 }}
                                axisLine={{ stroke: "#27272A" }}
                                tickLine={false}
                                tickFormatter={(v: number) => `${v.toFixed(1)}%`}
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
                                  `${Number(value).toFixed(2)}%`,
                                  "Drawdown",
                                ]}
                              />
                              <Area
                                type="monotone"
                                dataKey="drawdown"
                                stroke="#EF4444"
                                strokeWidth={2}
                                fill="url(#drawdownGrad)"
                              />
                            </AreaChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    </>
                  )
                })()}

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

                {/* ---- Trade P&L Distribution ---- */}
                {(() => {
                  const closedPnls = (result.events ?? [])
                    .filter((ev) => ev.type === "PositionClosed" && ev.data?.realized_pnl != null)
                    .map((ev, i) => ({
                      trade: i + 1,
                      pnl: Number(ev.data.realized_pnl),
                    }))
                  if (closedPnls.length === 0) return null
                  return (
                    <div className="rounded-lg border border-[#27272A] bg-[#18181B] p-4">
                      <h3 className="text-sm font-semibold text-[#A1A1AA] mb-4">
                        Trade P&amp;L Distribution
                      </h3>
                      <div className="h-[220px]">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={closedPnls}>
                            <CartesianGrid
                              strokeDasharray="3 3"
                              stroke="#27272A"
                              vertical={false}
                            />
                            <XAxis
                              dataKey="trade"
                              tick={{ fill: "#71717A", fontSize: 11 }}
                              axisLine={{ stroke: "#27272A" }}
                              tickLine={false}
                              label={{ value: "Trade #", position: "insideBottom", offset: -2, fill: "#71717A", fontSize: 11 }}
                            />
                            <YAxis
                              tick={{ fill: "#71717A", fontSize: 11 }}
                              axisLine={{ stroke: "#27272A" }}
                              tickLine={false}
                              tickFormatter={(v: number) => `$${v.toFixed(0)}`}
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
                                `$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
                                "P&L",
                              ]}
                            />
                            <Bar dataKey="pnl">
                              {closedPnls.map((entry, index) => (
                                <Cell
                                  key={index}
                                  fill={entry.pnl >= 0 ? "#10B981" : "#EF4444"}
                                />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  )
                })()}

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

          {/* ---- Strategy Comparison Table ---- */}
          {comparison && (
            <div className="mt-6 p-4 bg-[#18181B] rounded-xl border border-[#27272A]">
              <h3 className="text-sm font-semibold text-[#FAFAFA] mb-3">Strategy Comparison</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-[#71717A] border-b border-[#27272A]">
                      <th className="text-left py-2 px-2">Metric</th>
                      <th className="text-right py-2 px-2">Momentum</th>
                      <th className="text-right py-2 px-2">Mean Reversion</th>
                      <th className="text-right py-2 px-2">Breakout</th>
                    </tr>
                  </thead>
                  <tbody className="text-[#A1A1AA]">
                    {[
                      { label: "Total P&L", key: "total_pnl", fmt: (v: number) => `$${v.toLocaleString()}`, metric: false },
                      { label: "Win Rate", key: "win_rate", fmt: (v: number) => `${(v * 100).toFixed(1)}%`, metric: true },
                      { label: "Sharpe", key: "sharpe_ratio", fmt: (v: number) => v.toFixed(2), metric: true },
                      { label: "Max DD", key: "max_drawdown", fmt: (v: number) => `${(v * 100).toFixed(1)}%`, metric: true },
                      { label: "Trades", key: "total_trades", fmt: (v: number) => String(v), metric: true },
                      { label: "Profit Factor", key: "profit_factor", fmt: (v: number) => v < 0 ? "\u221E" : v.toFixed(2), metric: true },
                      { label: "Alpha", key: "alpha", fmt: (v: number) => `${(v * 100).toFixed(2)}%`, metric: false, benchmark: true },
                    ].map(({ label, key, fmt, metric, benchmark: isBenchmark }) => (
                      <tr key={key} className="border-b border-[#27272A]/50">
                        <td className="py-1.5 px-2 text-[#71717A]">{label}</td>
                        {comparison.map((r, i) => {
                          let val: number
                          if (isBenchmark) {
                            val = (r.benchmark as Record<string, number>)[key]
                          } else if (metric) {
                            val = (r.metrics as Record<string, number>)[key]
                          } else {
                            val = (r as unknown as Record<string, number>)[key]
                          }
                          return (
                            <td key={i} className={`py-1.5 px-2 text-right font-mono ${val > 0 ? "text-[#10B981]" : val < 0 ? "text-[#EF4444]" : "text-[#A1A1AA]"}`}>
                              {fmt(val)}
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
