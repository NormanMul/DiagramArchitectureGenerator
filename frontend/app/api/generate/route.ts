/**
 * BFF: forwards the browser's /api/generate to the backend Container App.
 * In production the BACKEND_API_URL is the internal ACA FQDN; locally it
 * defaults to http://localhost:8000.
 */
import { type NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND = process.env.BACKEND_API_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = await req.text();
  try {
    const upstream = await fetch(`${BACKEND}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      cache: "no-store",
    });
    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("Content-Type") ?? "application/json" },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: "Backend unreachable", detail: message }, { status: 502 });
  }
}
