import { NextResponse } from "next/server"

export async function GET() {
  return NextResponse.json({ events: [], total: 0 })
}
