import { type NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json({ status: "ok" });
}

export async function POST(_req: NextRequest) {
  // POST also accepted so a probe can use either verb.
  return NextResponse.json({ status: "ok" });
}
