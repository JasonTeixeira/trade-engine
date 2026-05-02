// ---------------------------------------------------------------------------
// Trade Engine — TypeScript backtest implementation
// ---------------------------------------------------------------------------

export interface Bar {
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface Signal {
  symbol: string
  side: "BUY" | "SELL"
  strength: number
}

export interface EngineEvent {
  id: string
  type: string
  timestamp: string
  data: Record<string, unknown>
}

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
    sortino_ratio: number
    calmar_ratio: number
    max_drawdown: number
    profit_factor: number
    avg_win: number
    avg_loss: number
    largest_win: number
    largest_loss: number
    consecutive_wins: number
    consecutive_losses: number
    recovery_factor: number
    avg_trade_duration: number
    skewness: number
    kurtosis: number
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

// ---------------------------------------------------------------------------
// Strategy implementations
// ---------------------------------------------------------------------------

function momentumStrategy(
  bars: Bar[],
  currentPosition: string | null
): Signal | null {
  if (bars.length < 20) return null
  const closes = bars.map((b) => b.close)
  const sma20 = closes.slice(-20).reduce((a, b) => a + b) / 20
  const price = closes[closes.length - 1]
  const threshold = sma20 * 0.002

  if (!currentPosition && price > sma20 + threshold) {
    return {
      symbol: "",
      side: "BUY",
      strength: Math.min(((price - sma20) / sma20) * 10, 1),
    }
  }
  if (currentPosition === "BUY" && price < sma20) {
    return { symbol: "", side: "SELL", strength: 0.8 }
  }
  return null
}

function meanReversionStrategy(
  bars: Bar[],
  currentPosition: string | null
): Signal | null {
  if (bars.length < 20) return null
  const closes = bars.map((b) => b.close)
  const sma = closes.slice(-20).reduce((a, b) => a + b) / 20
  const std = Math.sqrt(
    closes
      .slice(-20)
      .map((c) => (c - sma) ** 2)
      .reduce((a, b) => a + b) / 20
  )
  const price = closes[closes.length - 1]
  const zScore = (price - sma) / (std || 1)

  if (!currentPosition && zScore < -2) {
    return {
      symbol: "",
      side: "BUY",
      strength: Math.min(Math.abs(zScore) / 3, 1),
    }
  }
  if (currentPosition === "BUY" && zScore > 0) {
    return { symbol: "", side: "SELL", strength: 0.7 }
  }
  return null
}

function breakoutStrategy(
  bars: Bar[],
  currentPosition: string | null
): Signal | null {
  if (bars.length < 21) return null
  // Use PRIOR bars for channel — exclude current bar to avoid look-ahead
  const priorBars = bars.slice(-21, -1)
  const highs = priorBars.map((b) => b.high)
  const lows = priorBars.map((b) => b.low)
  const channelHigh = Math.max(...highs)
  const channelLow = Math.min(...lows)
  const price = bars[bars.length - 1].close

  if (!currentPosition && price > channelHigh) {
    const breakoutStrength = Math.min((price - channelHigh) / channelHigh * 50, 1)
    return { symbol: "", side: "BUY", strength: Math.max(0.5, breakoutStrength) }
  }
  if (currentPosition === "BUY" && price < channelLow) {
    return { symbol: "", side: "SELL", strength: 1.0 }
  }
  return null
}

// ---------------------------------------------------------------------------
// Main backtest function
// ---------------------------------------------------------------------------

export function runBacktest(config: BacktestConfig): BacktestResult {
  const strategyFn =
    config.strategy === "mean_reversion"
      ? meanReversionStrategy
      : config.strategy === "breakout"
        ? breakoutStrategy
        : momentumStrategy

  let capital = config.initial_capital
  const initialCapital = capital
  let peakEquity = capital
  let position: {
    side: string
    quantity: number
    entryPrice: number
  } | null = null
  const orders: BacktestResult["orders"] = []
  const events: EngineEvent[] = []
  const equityCurve: Array<{ bar: number; equity: number; price: number }> = []
  const closedPnls: number[] = []
  let eventCounter = 0

  const addEvent = (type: string, data: Record<string, unknown>) => {
    events.push({
      id: `EVT-${++eventCounter}`,
      type,
      timestamp: new Date().toISOString(),
      data,
    })
  }

  const bars: Bar[] = []

  for (let i = 0; i < config.prices.length; i++) {
    const price = config.prices[i]
    const bar: Bar = {
      open: price * 0.999,
      high: price * 1.001,
      low: price * 0.999,
      close: price,
      volume: 10000 + i * 50,
    }
    bars.push(bar)

    // Update unrealized P&L
    let unrealizedPnl = 0
    if (position) {
      unrealizedPnl =
        position.side === "BUY"
          ? (price - position.entryPrice) * position.quantity
          : (position.entryPrice - price) * position.quantity
    }

    const currentEquity = capital + unrealizedPnl
    equityCurve.push({
      bar: i,
      equity: Math.round(currentEquity * 100) / 100,
      price,
    })

    // Check drawdown halt
    if (currentEquity > peakEquity) peakEquity = currentEquity
    const drawdown = (peakEquity - currentEquity) / peakEquity
    // max_drawdown_pct arrives as a fraction (e.g., 0.10 for 10%) from the UI
    if (drawdown > config.max_drawdown_pct) continue

    // Get signal
    const currentPos = position ? position.side : null
    const signal = strategyFn(bars, currentPos)
    if (!signal) continue

    signal.symbol = config.symbol
    const orderId = `ORD-${String(orders.length + 1).padStart(4, "0")}`

    if (signal.side === "BUY" && !position) {
      // Calculate position size
      // max_position_pct arrives as a fraction (e.g., 0.05 for 5%) from the UI
      const maxNotional = currentEquity * config.max_position_pct
      const quantity = Math.max(
        1,
        Math.floor((maxNotional / price) * signal.strength)
      )

      // Apply slippage
      const slippage = price * (config.slippage_bps / 10000)
      const fillPrice = Math.round((price + slippage) * 100) / 100
      const cost = fillPrice * quantity + config.commission

      if (cost > capital) continue // insufficient funds

      capital -= cost
      position = { side: "BUY", quantity, entryPrice: fillPrice }

      orders.push({
        order_id: orderId,
        side: "BUY",
        quantity,
        state: "FILLED",
        fill_price: fillPrice,
        rejection_reason: null,
      })
      addEvent("OrderFilled", {
        order_id: orderId,
        side: "BUY",
        quantity,
        fill_price: fillPrice,
      })
      addEvent("PositionOpened", {
        symbol: config.symbol,
        side: "BUY",
        quantity,
        entry_price: fillPrice,
      })
    } else if (signal.side === "SELL" && position && position.side === "BUY") {
      // Close position
      const slippage = price * (config.slippage_bps / 10000)
      const fillPrice = Math.round((price - slippage) * 100) / 100
      const proceeds = fillPrice * position.quantity - config.commission
      const pnl = proceeds - position.entryPrice * position.quantity

      capital += proceeds
      closedPnls.push(pnl)

      orders.push({
        order_id: orderId,
        side: "SELL",
        quantity: position.quantity,
        state: "FILLED",
        fill_price: fillPrice,
        rejection_reason: null,
      })
      addEvent("OrderFilled", {
        order_id: orderId,
        side: "SELL",
        quantity: position.quantity,
        fill_price: fillPrice,
      })
      addEvent("PositionClosed", {
        symbol: config.symbol,
        realized_pnl: Math.round(pnl * 100) / 100,
      })

      position = null
    }
  }

  // Calculate metrics
  const wins = closedPnls.filter((p) => p > 0)
  const losses = closedPnls.filter((p) => p <= 0)
  const totalTrades = closedPnls.length
  const winRate = totalTrades > 0 ? wins.length / totalTrades : 0
  const avgWin =
    wins.length > 0 ? wins.reduce((a, b) => a + b, 0) / wins.length : 0
  const avgLoss =
    losses.length > 0 ? losses.reduce((a, b) => a + b, 0) / losses.length : 0
  const totalWins = wins.reduce((a, b) => a + b, 0)
  const totalLosses = Math.abs(losses.reduce((a, b) => a + b, 0))
  const profitFactor =
    totalLosses > 0 ? totalWins / totalLosses : totalWins > 0 ? Infinity : 0

  // Sharpe ratio — computed from bar-level equity returns (not per-trade P&L)
  let sharpe = 0
  if (equityCurve.length > 2) {
    const returns: number[] = []
    for (let i = 1; i < equityCurve.length; i++) {
      const prevEq = equityCurve[i - 1].equity
      if (prevEq > 0) {
        returns.push((equityCurve[i].equity - prevEq) / prevEq)
      }
    }
    if (returns.length > 1) {
      const meanRet = returns.reduce((a, b) => a + b, 0) / returns.length
      const stdRet = Math.sqrt(
        returns.map((r) => (r - meanRet) ** 2).reduce((a, b) => a + b) / (returns.length - 1)
      )
      sharpe = stdRet > 0 ? (meanRet / stdRet) * Math.sqrt(252) : 0
    }
  }

  // Max drawdown from equity curve
  let maxDD = 0
  let maxDDdollar = 0
  let eqPeak = equityCurve[0]?.equity || initialCapital
  for (const pt of equityCurve) {
    if (pt.equity > eqPeak) eqPeak = pt.equity
    const dd = (eqPeak - pt.equity) / eqPeak
    if (dd > maxDD) maxDD = dd
    const ddDollar = eqPeak - pt.equity
    if (ddDollar > maxDDdollar) maxDDdollar = ddDollar
  }

  // Sortino ratio — uses downside deviation only
  let sortino = 0
  if (equityCurve.length > 2) {
    const returns: number[] = []
    for (let i = 1; i < equityCurve.length; i++) {
      const prev = equityCurve[i - 1].equity
      if (prev > 0) returns.push((equityCurve[i].equity - prev) / prev)
    }
    if (returns.length > 1) {
      const meanR = returns.reduce((a, b) => a + b, 0) / returns.length
      const downside = returns.filter((r) => r < 0)
      const downsideDev = downside.length > 0
        ? Math.sqrt(downside.map((r) => r ** 2).reduce((a, b) => a + b) / downside.length)
        : 0
      sortino = downsideDev > 0 ? (meanR / downsideDev) * Math.sqrt(252) : 0
    }
  }

  // Current state
  let unrealizedPnl = 0
  if (position) {
    const lastPrice = config.prices[config.prices.length - 1]
    unrealizedPnl = (lastPrice - position.entryPrice) * position.quantity
  }
  const finalEquity = capital + unrealizedPnl

  // Calmar ratio — annualized return / max drawdown
  const totalReturn = (finalEquity - initialCapital) / initialCapital
  const barsPerYear = 252 * 6.5 // hourly bars in a trading year
  const years = config.prices.length / barsPerYear
  const annualizedReturn = years > 0 ? totalReturn / years : totalReturn
  const calmar = maxDD > 0 ? annualizedReturn / maxDD : 0

  // Consecutive wins/losses
  let maxConsecWins = 0, maxConsecLosses = 0, curWins = 0, curLosses = 0
  for (const pnl of closedPnls) {
    if (pnl > 0) { curWins++; curLosses = 0; maxConsecWins = Math.max(maxConsecWins, curWins) }
    else { curLosses++; curWins = 0; maxConsecLosses = Math.max(maxConsecLosses, curLosses) }
  }

  // Recovery factor — total profit / max drawdown $
  const totalProfit = closedPnls.reduce((a, b) => a + b, 0)
  const recoveryFactor = maxDDdollar > 0 ? totalProfit / maxDDdollar : 0

  // Avg trade duration (in bars)
  const avgTradeDuration = totalTrades > 0 ? config.prices.length / totalTrades : 0

  // Skewness and Kurtosis of trade P&L
  let skewness = 0, kurtosis = 0
  if (totalTrades > 2) {
    const mean = closedPnls.reduce((a, b) => a + b, 0) / totalTrades
    const std = Math.sqrt(closedPnls.map((p) => (p - mean) ** 2).reduce((a, b) => a + b) / (totalTrades - 1))
    if (std > 0) {
      skewness = closedPnls.map((p) => ((p - mean) / std) ** 3).reduce((a, b) => a + b) / totalTrades
      kurtosis = closedPnls.map((p) => ((p - mean) / std) ** 4).reduce((a, b) => a + b) / totalTrades - 3
    }
  }

  return {
    total_orders: orders.length,
    open_positions: position ? 1 : 0,
    equity: Math.round(finalEquity * 100) / 100,
    total_pnl: Math.round((finalEquity - initialCapital) * 100) / 100,
    unrealized_pnl: Math.round(unrealizedPnl * 100) / 100,
    realized_pnl:
      Math.round(closedPnls.reduce((a, b) => a + b, 0) * 100) / 100,
    metrics: {
      total_trades: totalTrades,
      win_rate: Math.round(winRate * 10000) / 10000,
      sharpe_ratio: Math.round(sharpe * 100) / 100,
      max_drawdown: Math.round(maxDD * 10000) / 10000,
      profit_factor:
        !isFinite(profitFactor)
          ? -1  // sentinel: frontend renders as "∞"
          : Math.round(profitFactor * 100) / 100,
      avg_win: Math.round(avgWin * 100) / 100,
      avg_loss: Math.round(avgLoss * 100) / 100,
      largest_win:
        wins.length > 0 ? Math.round(Math.max(...wins) * 100) / 100 : 0,
      largest_loss:
        losses.length > 0 ? Math.round(Math.min(...losses) * 100) / 100 : 0,
      sortino_ratio: Math.round(sortino * 100) / 100,
      calmar_ratio: Math.round(calmar * 100) / 100,
      consecutive_wins: maxConsecWins,
      consecutive_losses: maxConsecLosses,
      recovery_factor: Math.round(recoveryFactor * 100) / 100,
      avg_trade_duration: Math.round(avgTradeDuration),
      skewness: Math.round(skewness * 100) / 100,
      kurtosis: Math.round(kurtosis * 100) / 100,
    },
    orders,
    events_count: events.length,
    events,
    equity_curve: equityCurve,
  }
}
