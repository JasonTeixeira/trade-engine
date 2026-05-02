import { NextResponse } from "next/server"

export async function GET() {
  return NextResponse.json({
    total_orders: 0,
    open_positions: 0,
    equity: 0,
    total_pnl: 0,
    unrealized_pnl: 0,
    realized_pnl: 0,
  })
}
