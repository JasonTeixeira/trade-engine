import { NextResponse } from "next/server"

export async function GET() {
  const csv = "order_id,side,quantity,state,fill_price,rejection_reason\n"
  return new NextResponse(csv, {
    headers: {
      "Content-Type": "text/csv",
      "Content-Disposition": `attachment; filename="trade-engine-export-${Date.now()}.csv"`,
    },
  })
}
