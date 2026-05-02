import { NextResponse } from "next/server"

export async function GET() {
  return NextResponse.json({
    status: "ok",
    engine_active: true,
    strategies: ["momentum", "mean_reversion", "breakout"],
    timestamp: new Date().toISOString(),
  })
}
