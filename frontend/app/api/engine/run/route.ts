import { NextResponse } from "next/server"
import { runBacktest } from "@/lib/engine"

export async function POST(request: Request) {
  try {
    const config = await request.json()
    const result = runBacktest(config)
    return NextResponse.json(result)
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 400 })
  }
}
