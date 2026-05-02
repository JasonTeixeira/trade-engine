import { NextResponse } from "next/server"

export async function POST() {
  return NextResponse.json({
    status: "unavailable",
    message: "Connect Nexural Research locally to enable AI-powered analysis",
  })
}
