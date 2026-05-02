import { NextResponse } from "next/server"

export async function GET() {
  return NextResponse.json({
    available: false,
    url: "",
    message: "Connect Nexural Research locally",
  })
}
