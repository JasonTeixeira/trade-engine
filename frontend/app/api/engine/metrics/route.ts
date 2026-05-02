import { NextResponse } from "next/server"

export async function GET() {
  return NextResponse.json({
    total_trades: 0,
    win_rate: 0,
    sharpe_ratio: 0,
    max_drawdown: 0,
    profit_factor: 0,
    avg_win: 0,
    avg_loss: 0,
    largest_win: 0,
    largest_loss: 0,
  })
}
